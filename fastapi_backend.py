"""
FastAPI Backend Server & WebSocket Broker for CloudStack Template Automation.
Provides real-time task orchestration, WebSocket streaming, REST endpoints,
database persistence with SQLAlchemy, and AI error diagnosis integration.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import sessionmaker

from cloudstack_automation_implementation import (
    TemplateBuilder, Distribution, Hypervisor, PackageManager, Filesystem
)
from init_db import init_db, Execution, ExecutionStepRecord
from ai_advisor import AIAdvisor

# Setup Logging
logging.basicConfig(
    level=os.getenv("API_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("fastapi_backend")

# Initialize Database
engine = init_db()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize AI Advisor
advisor = AIAdvisor()


# ==================== PYDANTIC MODELS ====================

class HypervisorType(str, Enum):
    AUTO = "auto"
    KVM = "kvm"
    XEN = "xen"
    VMWARE = "vmware"
    HYPERV = "hyperv"
    PROXMOX = "proxmox"


class TemplateCreateRequest(BaseModel):
    ssh_host: str = Field(..., description="Target VM IP address or hostname")
    ssh_port: int = Field(22, ge=1, le=65535, description="SSH port")
    ssh_username: str = Field("root", description="SSH username with sudo/root access")
    ssh_password: Optional[str] = Field(None, description="SSH password")
    ssh_private_key: Optional[str] = Field(None, description="SSH private key content if using key auth")
    cloudstack_username: str = Field("centos", description="Default user created by cloud-init in template")
    hypervisor_type: HypervisorType = Field(HypervisorType.AUTO, description="Target hypervisor platform")


class StepUpdateModel(BaseModel):
    name: str
    description: Optional[str] = None
    command: Optional[str] = None
    status: str  # pending, running, completed, failed
    output: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None


class DiagnoseRequest(BaseModel):
    execution_id: str
    step_name: str
    command: str
    error_output: str


# ==================== EXECUTION MANAGER & WEBSOCKET BROKER ====================

class ConnectionManager:
    """Manages active WebSockets for real-time telemetry broadcast"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, execution_id: str, websocket: WebSocket):
        await websocket.accept()
        if execution_id not in self.active_connections:
            self.active_connections[execution_id] = []
        self.active_connections[execution_id].append(websocket)
        logger.info(f"WebSocket client connected to execution {execution_id}")

    def disconnect(self, execution_id: str, websocket: WebSocket):
        if execution_id in self.active_connections:
            try:
                self.active_connections[execution_id].remove(websocket)
                if not self.active_connections[execution_id]:
                    del self.active_connections[execution_id]
            except ValueError:
                pass
        logger.info(f"WebSocket client disconnected from execution {execution_id}")

    async def broadcast(self, execution_id: str, message: Dict[str, Any]):
        if execution_id in self.active_connections:
            websockets = list(self.active_connections[execution_id])
            for ws in websockets:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to client on {execution_id}: {e}")
                    self.disconnect(execution_id, ws)


ws_manager = ConnectionManager()


# ==================== BACKGROUND TASK WORKER ====================

def run_template_build_task(execution_id: str, request_data: dict, loop: asyncio.AbstractEventLoop):
    """Executes the template builder pipeline in background worker thread"""
    logger.info(f"Starting execution background job: {execution_id}")

    def on_event(event: Dict[str, Any]):
        # Broadcast asynchronously via loop
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast(execution_id, event),
            loop
        )

        # Update database
        event_type = event.get("type")
        db = SessionLocal()
        try:
            exec_record = db.query(Execution).filter(Execution.id == execution_id).first()
            if not exec_record:
                return

            if event_type == "environment_detected":
                exec_record.detected_environment = event.get("environment")
                db.commit()

            elif event_type == "step_update":
                step_data = event.get("step", {})
                step_name = step_data.get("name")
                step_rec = db.query(ExecutionStepRecord).filter(
                    ExecutionStepRecord.execution_id == execution_id,
                    ExecutionStepRecord.name == step_name
                ).first()

                if not step_rec:
                    step_rec = ExecutionStepRecord(
                        id=str(uuid.uuid4()),
                        execution_id=execution_id,
                        name=step_name,
                        description=step_data.get("description"),
                        command=step_data.get("command"),
                        status=step_data.get("status"),
                        output=step_data.get("output"),
                        error=step_data.get("error")
                    )
                    db.add(step_rec)
                else:
                    step_rec.status = step_data.get("status", step_rec.status)
                    step_rec.output = step_data.get("output", step_rec.output)
                    step_rec.error = step_data.get("error", step_rec.error)
                    if step_rec.status in ["completed", "failed"]:
                        step_rec.completed_at = datetime.utcnow()
                db.commit()

            elif event_type == "validation_update":
                exec_record.validation_checks = event.get("validation")
                db.commit()

            elif event_type == "execution_complete":
                status = event.get("status", "completed")
                exec_record.status = status
                if status == "completed":
                    result = event.get("result", {})
                    exec_record.validation_checks = result.get("validation")
                    exec_record.next_steps = result.get("next_steps")
                else:
                    exec_record.error_message = event.get("error")
                db.commit()

        except Exception as e:
            logger.error(f"Error persisting event {event_type} for {execution_id}: {e}")
            db.rollback()
        finally:
            db.close()

    builder = TemplateBuilder(
        ssh_host=request_data["ssh_host"],
        ssh_user=request_data["ssh_username"],
        ssh_pass=request_data.get("ssh_password"),
        ssh_port=request_data.get("ssh_port", 22),
        cloudstack_user=request_data.get("cloudstack_username", "centos"),
        event_callback=on_event
    )

    builder.build()


# ==================== FASTAPI APPLICATION ====================

app = FastAPI(
    title="CloudStack Template Automation API",
    description="AI-driven, dynamic template creation engine for Apache CloudStack",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== API ENDPOINTS ====================

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "CloudStack Template Automation",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@app.post("/api/template/create")
async def create_template(request: TemplateCreateRequest, background_tasks: BackgroundTasks):
    """Start an asynchronous template creation workflow"""
    execution_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        new_exec = Execution(
            id=execution_id,
            status="in_progress",
            ssh_host=request.ssh_host,
            ssh_port=str(request.ssh_port),
            ssh_username=request.ssh_username,
            cloudstack_username=request.cloudstack_username,
            hypervisor_type=request.hypervisor_type.value
        )
        db.add(new_exec)
        db.commit()
    finally:
        db.close()

    loop = asyncio.get_running_loop()
    background_tasks.add_task(run_template_build_task, execution_id, request.model_dump(), loop)

    return {
        "execution_id": execution_id,
        "status": "in_progress",
        "message": f"Template creation initiated for host {request.ssh_host}.",
        "websocket_url": f"/ws/template/{execution_id}"
    }


@app.get("/api/template/{execution_id}")
async def get_execution(execution_id: str):
    """Retrieve full execution telemetry, logs, and status"""
    db = SessionLocal()
    try:
        exec_record = db.query(Execution).filter(Execution.id == execution_id).first()
        if not exec_record:
            raise HTTPException(status_code=404, detail="Execution ID not found")
        return exec_record.to_dict()
    finally:
        db.close()


@app.get("/api/template")
async def list_executions(limit: int = 50, offset: int = 0):
    """List execution history"""
    db = SessionLocal()
    try:
        records = db.query(Execution).order_by(Execution.created_at.desc()).offset(offset).limit(limit).all()
        return [r.to_dict() for r in records]
    finally:
        db.close()


@app.post("/api/template/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    """Cancel an active execution"""
    db = SessionLocal()
    try:
        exec_record = db.query(Execution).filter(Execution.id == execution_id).first()
        if not exec_record:
            raise HTTPException(status_code=404, detail="Execution not found")
        if exec_record.status != "in_progress":
            raise HTTPException(status_code=400, detail=f"Cannot cancel execution with status: {exec_record.status}")
        
        exec_record.status = "cancelled"
        exec_record.error_message = "Cancelled by user request"
        db.commit()

        await ws_manager.broadcast(execution_id, {
            "type": "execution_complete",
            "status": "cancelled",
            "error": "Execution cancelled by operator."
        })
        return {"status": "cancelled", "execution_id": execution_id}
    finally:
        db.close()


@app.get("/api/distributions")
async def list_distributions():
    """List supported distributions and features"""
    return {
        "rhel_derivatives": [
            "Rocky Linux 8.x / 9.x",
            "AlmaLinux 8.x / 9.x",
            "CentOS Stream 8 / 9",
            "CentOS 7 (Legacy)",
            "Red Hat Enterprise Linux 7 / 8 / 9",
            "Fedora 38+"
        ],
        "debian_derivatives": [
            "Ubuntu 24.04 LTS (Noble Numbat)",
            "Ubuntu 22.04 LTS (Jammy Jellyfish)",
            "Ubuntu 20.04 LTS (Focal Fossa)",
            "Debian 12 (Bookworm)",
            "Debian 11 (Bullseye)"
        ],
        "others": [
            "openSUSE Leap 15+",
            "Alpine Linux 3.18+"
        ]
    }


@app.get("/api/hypervisors")
async def list_hypervisors():
    """List supported hypervisors"""
    return {
        "auto": "Auto-detect platform automatically (Recommended)",
        "kvm": "KVM / QEMU (Installs qemu-guest-agent)",
        "xen": "XenServer / XCP-ng (Installs xe-guest-utilities)",
        "vmware": "VMware vSphere (Installs open-vm-tools)",
        "hyperv": "Microsoft Hyper-V (Configures hyper-v daemons)",
        "proxmox": "Proxmox VE (Configures QEMU guest agent)"
    }


@app.post("/api/ai/diagnose")
async def diagnose_error(req: DiagnoseRequest):
    """Invoke AI Advisor to diagnose step failure and suggest remediation"""
    db = SessionLocal()
    try:
        exec_record = db.query(Execution).filter(Execution.id == req.execution_id).first()
        env = exec_record.detected_environment if exec_record and exec_record.detected_environment else {}
    finally:
        db.close()

    diagnosis = advisor.diagnose_error(
        step_name=req.step_name,
        command=req.command,
        error_output=req.error_output,
        environment=env
    )
    return diagnosis


# ==================== WEBSOCKET STREAMING ====================

@app.websocket("/ws/template/{execution_id}")
async def websocket_endpoint(websocket: WebSocket, execution_id: str):
    await ws_manager.connect(execution_id, websocket)
    db = SessionLocal()
    try:
        exec_record = db.query(Execution).filter(Execution.id == execution_id).first()
        if exec_record:
            await websocket.send_json({
                "type": "current_state",
                "execution": exec_record.to_dict()
            })
    finally:
        db.close()

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(execution_id, websocket)
    except Exception as e:
        logger.info(f"WebSocket closed: {e}")
        ws_manager.disconnect(execution_id, websocket)


# ==================== STATIC UI MOUNT ====================

static_path = Path(__file__).parent / "static"
if static_path.exists():
    assets_path = static_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    @app.get("/")
    async def serve_index():
        index_file = static_path / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "CloudStack Template Automation API is running."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fastapi_backend:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=True
    )
