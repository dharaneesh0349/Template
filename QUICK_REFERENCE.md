CloudStack Template Automation - Quick Reference Guide
📦 What You've Received
A complete, production-ready system for AI-driven CloudStack template automation with 6 core deliverables:
File 1: cloudstack_automation_prompt.md (1200+ lines)
What it is: Complete specification for an AI model to understand the entire system Why you need it:
If integrating Claude API or OpenAI for intelligent decisions
If training an AI model on template creation
For understanding the decision tree logic
For extending the system with new capabilities
Key sections:
System prompt directing AI behavior
Core directives (no fixed scripts, learn & adapt)
Workflow specification (6 phases)
Configuration file templates (with variables)
Critical decision logic (package manager selection, filesystem commands)
Error handling & fallbacks
Logging & decision tree tracking
Validation checklist
Use it: Feed this to Claude/GPT-4 for intelligent template creation

File 2: cloudstack_automation_implementation.py (700+ lines)
What it is: Production-ready Python code implementing the entire system Why you need it:
Core backend logic
All detection, generation, and execution code
Can run as-is or integrate with FastAPI
Key classes:
Distribution, PackageManager, Hypervisor, Filesystem (Enums)
EnvironmentDetector - Detects VM characteristics via SSH
ScriptGenerator - Generates adaptive scripts
SSHConnector - Secure SSH execution
TemplateBuilder - Main orchestrator
Use it:
# As standalone script
python cloudstack_automation_implementation.py

# Import into other projects
from cloudstack_automation_implementation import TemplateBuilder
builder = TemplateBuilder(host, user, pass)
result = builder.build()

File 3: fastapi_backend.py (500+ lines)
What it is: REST API and WebSocket server for the automation system Why you need it:
Provides REST API endpoints
WebSocket support for real-time updates
Execution management and logging
Async task processing
Key endpoints:
POST /api/template/create          - Start template creation
GET /api/template/{execution_id}   - Get execution status
GET /api/template                  - List all executions
WebSocket /ws/template/{id}        - Real-time status updates
GET /api/distributions             - List supported OS
GET /api/hypervisors               - List supported hypervisors
Use it:
# Start server
python -m uvicorn fastapi_backend:app --reload

# In your app
curl -X POST http://localhost:8000/api/template/create \
  -H "Content-Type: application/json" \
  -d '{
    "ssh_host": "192.168.1.100",
    "ssh_username": "root",
    "ssh_password": "password",
    "cloudstack_username": "centos"
  }'

File 4: react_frontend.tsx (700+ lines)
What it is: Complete React UI for the system Why you need it:
Professional web interface
Real-time progress monitoring
SSH credential form
WebSocket integration
Responsive design with Tailwind CSS
Key components:
TemplateCreateForm - SSH credentials & configuration
ExecutionMonitor - Real-time status display
TemplateAutomationApp - Main application
Use it:
# Integrate into React project
cp react_frontend.tsx src/components/

# Import in your app
import TemplateAutomationApp from './components/TemplateAutomation'

File 5: DEPLOYMENT_GUIDE.md (400+ lines)
What it is: Step-by-step deployment instructions Why you need it:
Complete backend setup (Python)
Frontend setup (React/Node)
Docker deployment
Kubernetes deployment
Database configuration
Security hardening
Monitoring setup
Troubleshooting
Key sections:
Prerequisites & requirements
Backend setup (5 steps)
Frontend setup (5 steps)
Production deployment (Docker/K8s)
Configuration & environment variables
Testing procedures
Monitoring & logging
Security considerations
Performance optimization
Backup & recovery
Use it: Follow step-by-step for production deployment

File 6: README.md (500+ lines)
What it is: Project overview and quick start guide Why you need it:
Understand the overall architecture
Quick 5-minute setup
Technology stack explanation
How the system works (6 phases)
Performance specifications
Troubleshooting guide
Future roadmap
Key sections:
Project overview
Architecture diagram
Quick start (5 minutes)
Technology stack table
Step-by-step workflow explanation
Monitoring metrics
Security considerations
Testing procedures

🚀 Implementation Paths
Path 1: Minimal Setup (30 minutes)
1. Read README.md (5 min)
2. Follow Quick Start (10 min)
3. Test with single VM (15 min)
Path 2: Complete Production (2-3 hours)
1. Read full README.md (15 min)
2. Follow DEPLOYMENT_GUIDE.md (45 min)
3. Deploy Docker containers (30 min)
4. Setup monitoring (20 min)
5. Security hardening (15 min)
6. Test end-to-end (20 min)
Path 3: AI Integration (1-2 hours)
1. Review cloudstack_automation_prompt.md (30 min)
2. Setup OpenAI/Claude API (15 min)
3. Modify fastapi_backend.py to call LLM (20 min)
4. Test intelligent decision making (30 min)

📋 Technology Stack at a Glance
Backend
Language:     Python 3.9+
Web:          FastAPI (async REST API)
SSH:          Paramiko (secure shell)
Config:       YAML (structured data)
Database:     PostgreSQL or SQLite
Task Queue:   Celery + Redis (optional)
LLM:          LangChain + Claude/OpenAI (optional)
Frontend
Framework:    React 18+ TypeScript
Styling:      Tailwind CSS
Icons:        Lucide React
HTTP:         Axios
Real-time:    WebSocket
Build:        Create React App
DevOps
Container:    Docker
Orchestration: Kubernetes (optional)
Monitoring:   Prometheus + Grafana (optional)
Logging:      ELK Stack (optional)

⚡ 5-Minute Quick Start
Terminal 1: Backend
cd cloudstack-automation
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn fastapi_backend:app --reload
# Backend running on http://localhost:8000
Terminal 2: Frontend
cd frontend
npm install
npm start
# Frontend running on http://localhost:3000
Terminal 3: Test
# Health check
curl http://localhost:8000/api/health

# Create template
curl -X POST http://localhost:8000/api/template/create \
  -H "Content-Type: application/json" \
  -d '{
    "ssh_host": "192.168.1.100",
    "ssh_username": "root",
    "ssh_password": "your_password",
    "cloudstack_username": "centos"
  }'
Browser
Open http://localhost:3000 and fill in form

🔧 Key Configuration Points
Environment Variables (.env)
# API
API_HOST=0.0.0.0
API_PORT=8000

# Database
DATABASE_URL=sqlite:///./data/app.db
# Or: postgresql://user:pass@localhost/dbname

# LLM (Optional)
OPENAI_API_KEY=sk-...
CLAUDE_API_KEY=sk-ant-...

# Security
SECRET_KEY=generate_with_secrets.token_urlsafe()
ALLOWED_ORIGINS=http://localhost:3000

# SSH
SSH_TIMEOUT=30
MAX_CONCURRENT_SSH=5
Python Requirements (requirements.txt)
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
paramiko==3.4.0
pyyaml==6.0.1
sqlalchemy==2.0.23
psycopg2-binary==2.9.9

🎯 Common Tasks
Task 1: Test Against Local CloudStack VM
1. Launch CloudStack VM (any RHEL/Debian-based)
2. Get VM's IP address
3. Open http://localhost:3000
4. Enter SSH credentials
5. Set cloudstack_username to "root" or "centos"
6. Click "Create Template"
7. Monitor in real-time
8. Verify in CloudStack UI
Task 2: Add New Distribution Support
1. Update EnvironmentDetector._detect_distribution()
2. Add Distribution enum value
3. Add conditional logic to ScriptGenerator methods
4. Test with VM running new distribution
Task 3: Deploy to Production
1. Follow DEPLOYMENT_GUIDE.md
2. Use Docker Compose or Kubernetes
3. Setup PostgreSQL database
4. Configure environment variables
5. Enable HTTPS
6. Setup monitoring with Prometheus
7. Add authentication/authorization
Task 4: Integrate with Claude API
1. Install openai library
2. Add to fastapi_backend.py:
   
   from langchain.chat_models import ChatOpenAI
   llm = ChatOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
   
3. In TemplateBuilderTask.handle_error():
   response = llm.predict(f"How to fix: {error}")
   
4. Set OPENAI_API_KEY in .env
5. Test error recovery

📊 Monitoring Checklist
Health Checks
# API health
curl http://localhost:8000/api/health

# Database connection
psql -U postgres -d cloudstack_automation -c "SELECT 1;"

# SSH connectivity
ssh -v root@<target-vm>

# WebSocket connectivity
wscat -c ws://localhost:8000/ws/template/<execution_id>
Logs to Watch
# Backend logs
tail -f /var/log/cloudstack-automation/backend.log

# Database logs
tail -f /var/log/postgresql/postgresql.log

# Target VM cloud-init logs
ssh root@<target-vm> "cloud-init status"
ssh root@<target-vm> "cat /var/log/cloud-init.log"
Metrics to Track
- Success rate (target: > 95%)
- Average execution time (target: < 60 sec)
- SSH timeout rate (target: 0%)
- Cloud-init installation success (target: 100%)
- WebSocket connection stability (target: 99%+)

🔒 Security Checklist
[ ] Use HTTPS in production (not HTTP)
[ ] Store SSH credentials in secure vault (not in DB)
[ ] Implement API key authentication
[ ] Enable rate limiting
[ ] CORS whitelist trusted domains only
[ ] Regular dependency updates
[ ] Database encryption at rest
[ ] Database connection SSL
[ ] SSH key rotation policy
[ ] Audit logging enabled
[ ] Regular security scanning
[ ] Input validation on all endpoints

🐛 Troubleshooting Quick Links
SSH Connection Issues
→ See DEPLOYMENT_GUIDE.md → Troubleshooting → SSH Connection Issues
Cloud-init Errors
→ See DEPLOYMENT_GUIDE.md → Troubleshooting → Cloud-init Configuration Errors
WebSocket Problems
→ See README.md → Troubleshooting → WebSocket Connection Lost
Performance Slow
→ See DEPLOYMENT_GUIDE.md → Performance Optimization

📞 Support Matrix
Issue
Solution
SSH fails
Check credentials, firewall, SSH service
cloud-init install fails
Check internet, repos, disk space
WebSocket disconnects
Check network, restart backend
Slow performance
Add resources, optimize DB queries
Template not created
Check CloudStack API, verify volume

📈 Next Steps
Immediate (Today)
[ ] Read README.md (understand the system)
[ ] Run 5-minute quick start
[ ] Test with single VM
[ ] Verify template creation works
Short-term (This Week)
[ ] Follow DEPLOYMENT_GUIDE.md
[ ] Deploy to staging environment
[ ] Setup monitoring
[ ] Test with multiple distributions
[ ] Document any customizations
Medium-term (This Month)
[ ] Production deployment
[ ] User training
[ ] Integration with CloudStack automation
[ ] Performance tuning
[ ] Security hardening
Long-term (This Quarter)
[ ] AI/LLM integration
[ ] Custom ansible playbooks
[ ] Multi-cloud support
[ ] Advanced error recovery
[ ] Knowledge base building

🎓 Learning Resources
Understanding the System
Start: README.md (Architecture section)
Deep dive: cloudstack_automation_prompt.md (Workflow section)
Implementation: cloudstack_automation_implementation.py
Technology Deep Dives
FastAPI: https://fastapi.tiangolo.com
Paramiko: https://www.paramiko.org
React: https://react.dev
cloud-init: https://cloud-init.io
Related Topics
CloudStack: https://cloudstack.apache.org
YAML: https://yaml.org
LLM Integration: https://python.langchain.com

💡 Pro Tips
For Development: Use SQLite for quick testing
For Production: Use PostgreSQL with connection pooling
For Speed: Run multiple async SSH operations
For Reliability: Implement exponential backoff on retries
For Debugging: Enable LOG_LEVEL=DEBUG and check cloud-init logs
For Monitoring: Export metrics to Prometheus
For AI: Start with Claude's API, then explore OpenAI

🚀 Getting Help
Question about architecture? → README.md
How to deploy? → DEPLOYMENT_GUIDE.md
What does the code do? → Read cloudstack_automation_implementation.py comments
How to integrate LLM? → cloudstack_automation_prompt.md
Still stuck? → Check DEPLOYMENT_GUIDE.md Troubleshooting section

✅ You're Now Ready To:
✅ Understand the complete system architecture ✅ Deploy it to your environment ✅ Automate CloudStack template creation ✅ Monitor templates in real-time ✅ Handle errors intelligently ✅ Extend with custom logic ✅ Integrate with AI/LLM models ✅ Scale to production workloads
Start with the README.md, then follow Quick Start. You'll have templates creating in 30 minutes.
Good luck! 🚀