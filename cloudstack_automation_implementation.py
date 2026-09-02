"""
CloudStack Template Automation - Python Implementation Engine
Dynamic, adaptive template creation for multiple Linux distributions and hypervisors.
Includes real-time progress callbacks, robust environment detection, LVM expansion,
hypervisor guest agent configuration, system sealing, and validation checks.
"""

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
import paramiko
import yaml


# ==================== ENUMS & DATA CLASSES ====================

class Distribution(str, Enum):
    CENTOS = "centos"
    ROCKY = "rocky"
    ALMALINUX = "almalinux"
    RHEL = "rhel"
    UBUNTU = "ubuntu"
    DEBIAN = "debian"
    FEDORA = "fedora"
    OPENSUSE = "opensuse"
    ALPINE = "alpine"
    AMAZON = "amazon"
    GENERIC_LINUX = "generic_linux"


class PackageManager(str, Enum):
    DNF = "dnf"
    YUM = "yum"
    APT = "apt"
    APT_GET = "apt-get"
    ZYPPER = "zypper"
    APK = "apk"
    UNKNOWN = "unknown"


class Hypervisor(str, Enum):
    KVM = "kvm"
    XEN = "xen"
    VMWARE = "vmware"
    HYPERV = "hyperv"
    PROXMOX = "proxmox"
    BAREMETAL = "baremetal"
    UNKNOWN = "unknown"


class Filesystem(str, Enum):
    XFS = "xfs"
    EXT4 = "ext4"
    EXT3 = "ext3"
    EXT2 = "ext2"
    BTRFS = "btrfs"
    UNKNOWN = "unknown"


@dataclass
class Disk:
    """Represents a detected disk or partition"""
    name: str
    size: str
    type: str  # disk, part, lvm
    mountpoint: str
    parent: Optional[str] = None


@dataclass
class LVMInfo:
    """Represents LVM Logical Volume configuration"""
    lv_path: str
    vg_name: str
    pv_path: str
    pv_size: str
    lv_size: str = ""


@dataclass
class EnvironmentInfo:
    """Complete detected environment profile"""
    distribution: Distribution
    version: str
    package_manager: PackageManager
    hypervisor: Hypervisor
    boot_partition: str
    root_partition: str
    root_lv: Optional[LVMInfo]
    filesystem_type: Filesystem
    root_mountpoint: str
    all_disks: List[Disk]
    cloud_init_installed: bool
    cloud_init_version: Optional[str]
    kernel_version: str = ""
    ip_addresses: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['distribution'] = self.distribution.value
        d['package_manager'] = self.package_manager.value
        d['hypervisor'] = self.hypervisor.value
        d['filesystem_type'] = self.filesystem_type.value
        return d


@dataclass
class ExecutionStep:
    """Represents a single execution step in the pipeline"""
    name: str
    command: str
    description: str
    critical: bool = True


# ==================== SSH CONNECTOR ====================

class SSHConnector:
    """Handles SSH connections, command execution, and real-time streaming"""

    def __init__(self, host: str, username: str, password: Optional[str] = None,
                 key_filename: Optional[str] = None, port: int = 22, timeout: int = 30):
        self.host = host
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
        self.logger = logging.getLogger("ssh_connector")

    def connect(self):
        """Establish SSH connection with auto-retry"""
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "timeout": self.timeout,
            "banner_timeout": 30,
            "auth_timeout": 20
        }

        if self.key_filename:
            connect_kwargs["key_filename"] = self.key_filename
        if self.password:
            connect_kwargs["password"] = self.password

        last_error = None
        for attempt in range(1, 4):
            try:
                self.logger.info(f"Connecting to {self.username}@{self.host}:{self.port} (Attempt {attempt}/3)...")
                self.client.connect(**connect_kwargs)
                self.logger.info(f"✓ SSH connection established to {self.host}")
                return
            except Exception as e:
                last_error = e
                self.logger.warning(f"SSH connection attempt {attempt} failed: {e}")
                if attempt < 3:
                    time.sleep(2)

        raise ConnectionError(f"Failed to connect to SSH host {self.host}:{self.port} after 3 attempts: {last_error}")

    def wrap_sudo(self, command: str) -> str:
        """Wrap command with sudo if connected as non-root user"""
        if self.username == "root":
            return command
        # Non-root user: use sudo with password fallback if password provided
        if self.password:
            escaped_cmd = command.replace("'", "'\"'\"'")
            escaped_pw = self.password.replace("'", "'\"'\"'")
            return f"echo '{escaped_pw}' | sudo -S -p '' -- bash -c '{escaped_cmd}'"
        else:
            escaped_cmd = command.replace("'", "'\"'\"'")
            return f"sudo -n -- bash -c '{escaped_cmd}'"

    def execute(self, command: str, stream_callback: Optional[Callable[[str], None]] = None, sudo: bool = False) -> str:
        """Execute command via SSH with streaming or buffered output capture"""
        if not self.client or not self.client.get_transport() or not self.client.get_transport().is_active():
            self.connect()

        cmd_to_run = self.wrap_sudo(command) if (sudo and self.username != "root") else command
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd_to_run, get_pty=True)
            output_lines = []

            # Read stream
            while True:
                line = stdout.readline()
                if not line:
                    break
                line_str = line.rstrip('\r\n')
                output_lines.append(line_str)
                if stream_callback:
                    stream_callback(line_str)

            exit_status = stdout.channel.recv_exit_status()
            full_output = "\n".join(output_lines)
            err_output = stderr.read().decode('utf-8', errors='replace').strip()

            if exit_status != 0:
                self.logger.warning(f"Command '{command[:60]}' returned status {exit_status}: {err_output or full_output[:200]}")

            return full_output
        except Exception as e:
            self.logger.error(f"SSH command execution failed on {self.host}: {e}")
            raise

    def disconnect(self):
        """Safely close SSH session"""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
            self.logger.info(f"SSH session closed for {self.host}")


# ==================== DETECTION MODULE ====================

class EnvironmentDetector:
    """Intelligently detects VM characteristics via SSH"""

    DETECTION_SCRIPTS = {
        'distribution': """
            if [ -f /etc/os-release ]; then
                cat /etc/os-release
            elif [ -f /etc/redhat-release ]; then
                cat /etc/redhat-release
            elif [ -f /etc/debian_version ]; then
                echo "ID=debian"
                echo "VERSION_ID=$(cat /etc/debian_version)"
            else
                uname -a
            fi
        """,
        'hypervisor': """
            if command -v systemd-detect-virt &>/dev/null; then
                systemd-detect-virt
            fi
            dmidecode -s system-manufacturer 2>/dev/null || true
            dmidecode -s system-product-name 2>/dev/null || true
            grep -E -i "(qemu|kvm|vmware|xen|hyper-v|virtualbox)" /proc/cpuinfo /proc/version 2>/dev/null || true
        """,
        'disks': 'lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,PKNAME 2>/dev/null || lsblk -o NAME,SIZE,TYPE,MOUNTPOINT',
        'lvm_lv': 'lvdisplay -c 2>/dev/null || true',
        'lvm_pv': 'pvdisplay -c 2>/dev/null || true',
        'lvm_vg': 'vgdisplay -c 2>/dev/null || true',
        'filesystems': 'df -hT --output=target,fstype 2>/dev/null || df -T',
        'cloud_init': 'cloud-init --version 2>/dev/null || echo "not_installed"',
        'package_manager': """
            if command -v dnf &>/dev/null; then echo "dnf"
            elif command -v yum &>/dev/null; then echo "yum"
            elif command -v apt-get &>/dev/null; then echo "apt-get"
            elif command -v apt &>/dev/null; then echo "apt"
            elif command -v zypper &>/dev/null; then echo "zypper"
            elif command -v apk &>/dev/null; then echo "apk"
            else echo "unknown"
            fi
        """,
        'kernel': 'uname -r',
        'ip_addresses': 'ip -o -4 addr show 2>/dev/null | awk \'{print $4}\' | cut -d/ -f1 || hostname -I'
    }

    def __init__(self, ssh_client: SSHConnector):
        self.ssh = ssh_client
        self.logger = logging.getLogger("environment_detector")

    def detect_all(self) -> EnvironmentInfo:
        """Run all telemetry probes and construct EnvironmentInfo"""
        self.logger.info("Executing environment probes across target VM...")

        dist_info = self._detect_distribution()
        pkg_mgr = self._detect_package_manager()
        hypervisor = self._detect_hypervisor()
        disks = self._detect_disks()
        lvm_info_dict = self._detect_lvm()
        filesystems = self._detect_filesystems()
        cloud_init = self._detect_cloud_init()
        kernel = self.ssh.execute(self.DETECTION_SCRIPTS['kernel']).strip()
        ips = [ip.strip() for ip in self.ssh.execute(self.DETECTION_SCRIPTS['ip_addresses']).split() if ip.strip()]

        root_partition, root_mountpoint = self._find_root_partition(disks)
        root_lv = self._match_root_lv(root_partition, lvm_info_dict)
        fs_type = self._get_fs_type(root_mountpoint, filesystems)
        boot_part = self._find_boot_partition(disks) or root_partition

        env = EnvironmentInfo(
            distribution=dist_info['distribution'],
            version=dist_info['version'],
            package_manager=pkg_mgr,
            hypervisor=hypervisor,
            boot_partition=boot_part,
            root_partition=root_partition,
            root_lv=root_lv,
            filesystem_type=fs_type,
            root_mountpoint=root_mountpoint,
            all_disks=disks,
            cloud_init_installed=cloud_init['installed'],
            cloud_init_version=cloud_init['version'],
            kernel_version=kernel,
            ip_addresses=ips
        )

        self.logger.info(f"✓ Probe complete: {env.distribution.value} {env.version} on {env.hypervisor.value} ({fs_type.value})")
        return env

    def _detect_distribution(self) -> Dict[str, Any]:
        output = self.ssh.execute(self.DETECTION_SCRIPTS['distribution'])
        dist_id = "linux"
        version_id = "unknown"
        id_like = ""

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("ID="):
                dist_id = line.split("=", 1)[1].strip('"\'').lower()
            elif line.startswith("VERSION_ID="):
                version_id = line.split("=", 1)[1].strip('"\'')
            elif line.startswith("ID_LIKE="):
                id_like = line.split("=", 1)[1].strip('"\'').lower()

        dist_map = {
            "centos": Distribution.CENTOS,
            "rocky": Distribution.ROCKY,
            "almalinux": Distribution.ALMALINUX,
            "rhel": Distribution.RHEL,
            "redhat": Distribution.RHEL,
            "ubuntu": Distribution.UBUNTU,
            "debian": Distribution.DEBIAN,
            "fedora": Distribution.FEDORA,
            "opensuse": Distribution.OPENSUSE,
            "sles": Distribution.OPENSUSE,
            "alpine": Distribution.ALPINE,
            "amzn": Distribution.AMAZON,
        }

        distribution = dist_map.get(dist_id)
        if not distribution:
            if "rhel" in id_like or "centos" in id_like or "fedora" in id_like:
                distribution = Distribution.ROCKY
            elif "debian" in id_like or "ubuntu" in id_like:
                distribution = Distribution.UBUNTU
            else:
                distribution = Distribution.GENERIC_LINUX

        return {
            "distribution": distribution,
            "version": version_id
        }

    def _detect_package_manager(self) -> PackageManager:
        output = self.ssh.execute(self.DETECTION_SCRIPTS['package_manager']).strip().lower()
        if "dnf" in output:
            return PackageManager.DNF
        elif "yum" in output:
            return PackageManager.YUM
        elif "apt-get" in output or "apt" in output:
            return PackageManager.APT_GET
        elif "zypper" in output:
            return PackageManager.ZYPPER
        elif "apk" in output:
            return PackageManager.APK
        return PackageManager.UNKNOWN

    def _detect_hypervisor(self) -> Hypervisor:
        output = self.ssh.execute(self.DETECTION_SCRIPTS['hypervisor']).lower()
        if "kvm" in output or "qemu" in output or "bochs" in output:
            return Hypervisor.KVM
        elif "xen" in output or "xcp" in output:
            return Hypervisor.XEN
        elif "vmware" in output:
            return Hypervisor.VMWARE
        elif "microsoft" in output or "hyper-v" in output or "hyperv" in output:
            return Hypervisor.HYPERV
        elif "proxmox" in output:
            return Hypervisor.PROXMOX
        elif "none" in output or "bare" in output:
            return Hypervisor.BAREMETAL
        return Hypervisor.KVM  # Default to KVM as standard CloudStack hypervisor

    def _detect_disks(self) -> List[Disk]:
        output = self.ssh.execute(self.DETECTION_SCRIPTS['disks'])
        disks = []
        try:
            data = json.loads(output)
            for dev in data.get('blockdevices', []):
                self._parse_json_block_device(dev, disks, parent=None)
            return disks
        except Exception:
            # Fallback text parsing for lsblk
            for line in output.splitlines():
                parts = line.split()
                if len(parts) >= 4 and not parts[0].startswith("NAME"):
                    disks.append(Disk(
                        name=parts[0].replace("├─", "").replace("└─", "").replace("│", "").strip(),
                        size=parts[1] if len(parts) > 1 else "",
                        type=parts[2] if len(parts) > 2 else "part",
                        mountpoint=parts[3] if len(parts) > 3 else ""
                    ))
        return disks

    def _parse_json_block_device(self, dev: Dict[str, Any], disks: List[Disk], parent: Optional[str] = None):
        name = dev.get('name', '')
        # full path format
        full_name = f"/dev/{name}" if not name.startswith("/dev/") else name
        disk = Disk(
            name=full_name,
            size=str(dev.get('size', '')),
            type=str(dev.get('type', '')),
            mountpoint=str(dev.get('mountpoint', '') or ''),
            parent=parent
        )
        disks.append(disk)
        for child in dev.get('children', []):
            self._parse_json_block_device(child, disks, parent=full_name)

    def _detect_lvm(self) -> Dict[str, LVMInfo]:
        lv_output = self.ssh.execute(self.DETECTION_SCRIPTS['lvm_lv'])
        pv_output = self.ssh.execute(self.DETECTION_SCRIPTS['lvm_pv'])
        lvm_dict = {}

        # Parse PVs
        pvs = []
        for line in pv_output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(':')
            if len(parts) >= 3:
                pvs.append({"pv_path": parts[0].strip(), "vg_name": parts[1].strip(), "pv_size": parts[2].strip()})

        # Parse LVs
        for line in lv_output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(':')
            if len(parts) >= 2:
                lv_path = parts[0].strip()
                vg_name = parts[1].strip()
                matching_pv = next((p["pv_path"] for p in pvs if p["vg_name"] == vg_name), "/dev/vda2")
                matching_pv_size = next((p["pv_size"] for p in pvs if p["vg_name"] == vg_name), "")
                lvm_dict[lv_path] = LVMInfo(
                    lv_path=lv_path,
                    vg_name=vg_name,
                    pv_path=matching_pv,
                    pv_size=matching_pv_size
                )
        return lvm_dict

    def _detect_filesystems(self) -> Dict[str, str]:
        output = self.ssh.execute(self.DETECTION_SCRIPTS['filesystems'])
        fs_dict = {}
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("TARGET") or line.startswith("Filesystem"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                mountpoint = parts[0]
                fstype = parts[1].lower()
                fs_dict[mountpoint] = fstype
        return fs_dict

    def _detect_cloud_init(self) -> Dict[str, Any]:
        output = self.ssh.execute(self.DETECTION_SCRIPTS['cloud_init']).strip()
        if "not_installed" in output or "command not found" in output:
            return {"installed": False, "version": None}
        v_match = re.search(r'(\d+\.\d+(\.\d+)?)', output)
        return {
            "installed": True,
            "version": v_match.group(1) if v_match else output
        }

    def _find_root_partition(self, disks: List[Disk]) -> Tuple[str, str]:
        for disk in disks:
            if disk.mountpoint == '/':
                return disk.name, '/'
        # Fallback query
        root_dev = self.ssh.execute("findmnt -n -o SOURCE / 2>/dev/null || df / | tail -1 | awk '{print $1}'").strip()
        return root_dev or "/dev/vda1", "/"

    def _find_boot_partition(self, disks: List[Disk]) -> Optional[str]:
        for disk in disks:
            if disk.mountpoint == '/boot':
                return disk.name
        return None

    def _match_root_lv(self, root_partition: str, lvm_dict: Dict[str, LVMInfo]) -> Optional[LVMInfo]:
        if not lvm_dict:
            return None
        for lv_path, lv_info in lvm_dict.items():
            clean_part = root_partition.replace("-", "").replace("/", "").lower()
            clean_lv = lv_path.replace("-", "").replace("/", "").lower()
            if clean_lv in clean_part or clean_part in clean_lv or "root" in lv_path.lower():
                return lv_info
        if len(lvm_dict) == 1:
            return next(iter(lvm_dict.values()))
        return None

    def _get_fs_type(self, mountpoint: str, filesystems: Dict[str, str]) -> Filesystem:
        fs = filesystems.get(mountpoint, "").lower()
        if "xfs" in fs:
            return Filesystem.XFS
        elif "ext4" in fs:
            return Filesystem.EXT4
        elif "ext3" in fs:
            return Filesystem.EXT3
        elif "btrfs" in fs:
            return Filesystem.BTRFS
        return Filesystem.EXT4


# ==================== SCRIPT GENERATOR ====================

class ScriptGenerator:
    """Generates distribution- and hypervisor-aware scripts and configs"""

    def __init__(self, env: EnvironmentInfo, cloudstack_username: str = "centos"):
        self.env = env
        self.username = cloudstack_username
        self.logger = logging.getLogger("script_generator")

    def generate_base_system_config(self) -> ExecutionStep:
        """Update packages and establish clean hostname"""
        cmds = []
        if self.env.package_manager == PackageManager.DNF:
            cmds.append("dnf clean all && dnf update -y --setopt=install_weak_deps=False")
        elif self.env.package_manager == PackageManager.YUM:
            cmds.append("yum clean all && yum update -y")
        elif self.env.package_manager in [PackageManager.APT, PackageManager.APT_GET]:
            cmds.extend([
                "export DEBIAN_FRONTEND=noninteractive",
                "apt-get update -y",
                "apt-get upgrade -y -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold'"
            ])
        cmds.extend([
            "hostnamectl set-hostname localhost 2>/dev/null || echo 'localhost' > /etc/hostname",
            "sed -i '/127.0.1.1/d' /etc/hosts 2>/dev/null || true",
            "sed -i 's/^#\\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config 2>/dev/null || true",
            "mkdir -p /etc/ssh/sshd_config.d 2>/dev/null && echo 'PasswordAuthentication yes' > /etc/ssh/sshd_config.d/60-cloudstack.conf 2>/dev/null || true"
        ])
        return ExecutionStep(
            name="Base System Configuration & Updates",
            command=" && ".join(cmds),
            description="Update package manager metadata and configure clean hostname",
            critical=True
        )

    def generate_cloud_init_install(self) -> ExecutionStep:
        """Install cloud-init and cloud-utils-growpart"""
        cmds = []
        if self.env.package_manager == PackageManager.DNF:
            cmds.append("dnf install -y cloud-init cloud-utils-growpart wget curl")
        elif self.env.package_manager == PackageManager.YUM:
            cmds.append("yum install -y epel-release 2>/dev/null || true && yum install -y cloud-init cloud-utils-growpart wget curl")
        elif self.env.package_manager in [PackageManager.APT, PackageManager.APT_GET]:
            cmds.extend([
                "export DEBIAN_FRONTEND=noninteractive",
                "apt-get install -y cloud-init cloud-initramfs-growroot cloud-guest-utils wget curl"
            ])
        else:
            cmds.append("echo 'Skipping native package manager install'")
        return ExecutionStep(
            name="Cloud-init & Utility Package Installation",
            command=" && ".join(cmds),
            description="Install cloud-init, partition growth utilities, and HTTP tools",
            critical=True
        )

    def generate_cloud_init_configs(self) -> List[Tuple[str, str]]:
        """Synthesize YAML configs tailored for CloudStack datasource and VM spec"""
        configs = []

        # 99_cloudstack.cfg
        cloudstack_cfg = {
            "datasource_list": ["CloudStack", "None"],
            "datasource": {
                "CloudStack": {
                    "max_wait": 120,
                    "timeout": 10
                },
                "None": {}
            }
        }
        configs.append((
            "/etc/cloud/cloud.cfg.d/99_cloudstack.cfg",
            yaml.dump(cloudstack_cfg, default_flow_style=False)
        ))

        # 80_user.cfg
        user_cfg = {
            "system_info": {
                "default_user": {
                    "name": self.username,
                    "lock_passwd": False,
                    "sudo": ["ALL=(ALL) NOPASSWD:ALL"],
                    "shell": "/bin/bash"
                }
            },
            "disable_root": False,
            "ssh_pwauth": True,
            "preserve_hostname": False,
            "chpasswd": {
                "expire": False
            }
        }
        configs.append((
            "/etc/cloud/cloud.cfg.d/80_user.cfg",
            yaml.dump(user_cfg, default_flow_style=False)
        ))

        # 49_hostkeys.cfg
        configs.append((
            "/etc/cloud/cloud.cfg.d/49_hostkeys.cfg",
            "ssh_deletekeys: true\nssh_genkeytypes: ['rsa', 'ecdsa', 'ed25519']\n"
        ))

        # 50_growpartition.cfg
        growpart_cfg = {
            "growpart": {
                "mode": "auto",
                "devices": [self.env.root_partition],
                "ignore_growroot_disabled": False
            }
        }
        configs.append((
            "/etc/cloud/cloud.cfg.d/50_growpartition.cfg",
            yaml.dump(growpart_cfg, default_flow_style=False)
        ))

        # 51_extend_volume.cfg (for LVM)
        if self.env.root_lv:
            fs_cmd = "xfs_growfs /" if self.env.filesystem_type == Filesystem.XFS else f"resize2fs {self.env.root_lv.lv_path}"
            extend_cfg = {
                "runcmd": [
                    ["cloud-init-per", "once", "grow_pv", "pvresize", self.env.root_lv.pv_path],
                    ["cloud-init-per", "once", "grow_lv", "lvresize", "-l", "+100%FREE", self.env.root_lv.lv_path],
                    ["cloud-init-per", "once", "grow_fs", "sh", "-c", fs_cmd]
                ]
            }
            configs.append((
                "/etc/cloud/cloud.cfg.d/51_extend_volume.cfg",
                yaml.dump(extend_cfg, default_flow_style=False)
            ))

        return configs

    def generate_guest_agent_install(self) -> ExecutionStep:
        """Hypervisor-specific guest agent provisioning"""
        cmds = []
        hyper = self.env.hypervisor

        if hyper in [Hypervisor.KVM, Hypervisor.PROXMOX, Hypervisor.UNKNOWN]:
            if self.env.package_manager == PackageManager.DNF:
                cmds.append("dnf install -y qemu-guest-agent && systemctl enable qemu-guest-agent && systemctl restart qemu-guest-agent || true")
            elif self.env.package_manager == PackageManager.YUM:
                cmds.append("yum install -y qemu-guest-agent && systemctl enable qemu-guest-agent && systemctl restart qemu-guest-agent || true")
            else:
                cmds.append("apt-get install -y qemu-guest-agent && systemctl enable qemu-guest-agent && systemctl restart qemu-guest-agent || true")
        elif hyper == Hypervisor.XEN:
            if self.env.package_manager in [PackageManager.DNF, PackageManager.YUM]:
                cmds.append("yum install -y xe-guest-utilities || dnf install -y xe-guest-utilities-latest || true")
            else:
                cmds.append("apt-get install -y xe-guest-utilities || true")
            cmds.append("systemctl enable xe-daemon 2>/dev/null || true")
        elif hyper == Hypervisor.VMWARE:
            if self.env.package_manager in [PackageManager.DNF, PackageManager.YUM]:
                cmds.append("dnf install -y open-vm-tools || yum install -y open-vm-tools")
            else:
                cmds.append("apt-get install -y open-vm-tools")
            cmds.append("systemctl enable vmtoolsd 2>/dev/null || true")
        else:
            cmds.append("echo 'No specific guest agent required'")

        return ExecutionStep(
            name=f"Install & Enable {hyper.value.upper()} Guest Agent",
            command=" && ".join(cmds),
            description=f"Provision hypervisor guest management utilities for {hyper.value}",
            critical=False
        )

    def generate_cloud_init_enablement(self) -> ExecutionStep:
        """Enable systemd cloud-init units in proper boot sequence"""
        cmds = [
            "rm -f /etc/cloud/cloud-init.disabled 2>/dev/null || true",
            "systemctl enable cloud-init-local.service 2>/dev/null || true",
            "systemctl enable cloud-init.service 2>/dev/null || true",
            "systemctl enable cloud-config.service 2>/dev/null || true",
            "systemctl enable cloud-final.service 2>/dev/null || true"
        ]
        return ExecutionStep(
            name="Enable Cloud-init Services",
            command=" && ".join(cmds),
            description="Configure systemd service targets for cloud-init boot phases",
            critical=True
        )

    def generate_deep_sealing_script(self) -> ExecutionStep:
        """Comprehensive system sanitization & sealing for golden template snapshot"""
        cmds = [
            # Remove Subiquity installer overrides that disable cloud-init networking & datasources
            "rm -f /etc/cloud/cloud.cfg.d/00-subiquity* /etc/cloud/cloud.cfg.d/99-installer.cfg /etc/cloud/cloud.cfg.d/subiquity* 2>/dev/null || true",
            # Cloud-init state clean
            "cloud-init clean --logs --seed 2>/dev/null || rm -rf /var/lib/cloud/*",
            "rm -rf /var/log/cloud-init*.log /var/log/cloud-init* 2>/dev/null || true",
            # Network MAC & Udev rules clean
            "rm -f /etc/udev/rules.d/70-persistent-net.rules /etc/udev/rules.d/70* 2>/dev/null || true",
            "rm -f /var/lib/dhcp/* /var/lib/dhclient/* /var/lib/NetworkManager/* 2>/dev/null || true",
            "sed -i '/^\\(HWADDR\\|UUID\\)=/d' /etc/sysconfig/network-scripts/ifcfg-* 2>/dev/null || true",
            # Machine-ID clean
            "truncate -s 0 /etc/machine-id 2>/dev/null || true",
            "rm -f /var/lib/dbus/machine-id 2>/dev/null || true",
            "ln -sf /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null || true",
            # SSH host keys removal (regenerated on first boot)
            "rm -f /etc/ssh/ssh_host_* 2>/dev/null || true",
            # Temporary files & logs wipe
            "rm -rf /tmp/* /var/tmp/* 2>/dev/null || true",
            "cat /dev/null > /var/log/wtmp 2>/dev/null || true",
            "cat /dev/null > /var/log/lastlog 2>/dev/null || true",
            "find /var/log -type f -exec truncate -s 0 {} + 2>/dev/null || true",
            # Shell history wipe
            "history -c 2>/dev/null || true",
            "> /root/.bash_history 2>/dev/null || true",
            f"> /home/{self.username}/.bash_history 2>/dev/null || true",
            "sync"
        ]
        return ExecutionStep(
            name="Deep System Sealing & Sanitization",
            command="; ".join(cmds),
            description="Remove machine-id, network MAC persistence, logs, and temporary keys",
            critical=True
        )


# ==================== EXECUTION ORCHESTRATOR ====================

class TemplateBuilder:
    """Main orchestrator for end-to-end template generation with real-time events"""

    def __init__(self, ssh_host: str, ssh_user: str, ssh_pass: Optional[str] = None,
                 ssh_key_filename: Optional[str] = None, ssh_port: int = 22,
                 cloudstack_user: str = "centos",
                 event_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.ssh = SSHConnector(ssh_host, ssh_user, password=ssh_pass,
                                key_filename=ssh_key_filename, port=ssh_port)
        self.cloudstack_user = cloudstack_user
        self.event_callback = event_callback
        self.logger = logging.getLogger("template_builder")
        self.execution_log: List[Dict[str, Any]] = []

    def _emit(self, event_type: str, data: Dict[str, Any]):
        """Dispatch event to callback listener"""
        payload = {"type": event_type, "timestamp": datetime.utcnow().isoformat(), **data}
        if self.event_callback:
            try:
                self.event_callback(payload)
            except Exception as e:
                self.logger.warning(f"Error invoking event callback: {e}")

    def build(self) -> Dict[str, Any]:
        """Execute complete template orchestration pipeline"""
        try:
            self._emit("phase_change", {"phase": "connecting", "message": f"Establishing SSH connection to {self.ssh.host}:{self.ssh.port}..."})
            self.ssh.connect()

            # Phase 1: Environment Detection
            self._emit("phase_change", {"phase": "detection", "message": "Probing target VM environment characteristics..."})
            detector = EnvironmentDetector(self.ssh)
            environment = detector.detect_all()
            self._emit("environment_detected", {"environment": environment.to_dict()})

            # Phase 2: Planning & Script Generation
            self._emit("phase_change", {"phase": "planning", "message": "Synthesizing distribution-specific configuration plan..."})
            generator = ScriptGenerator(environment, self.cloudstack_user)

            execution_plan = [
                generator.generate_base_system_config(),
                generator.generate_cloud_init_install(),
                generator.generate_guest_agent_install(),
                generator.generate_cloud_init_enablement()
            ]

            # Phase 3: Step-by-Step Command Execution
            self._emit("phase_change", {"phase": "execution", "message": "Executing setup and package provisioning..."})
            for step in execution_plan:
                self._execute_step(step)

            # Phase 4: Config Files Deployment
            self._emit("phase_change", {"phase": "configuration", "message": "Writing CloudStack cloud-init configuration files..."})
            self._deploy_config_files(generator)

            # Phase 5: System Sealing
            self._emit("phase_change", {"phase": "sealing", "message": "Performing deep system sealing and sanitization..."})
            sealing_step = generator.generate_deep_sealing_script()
            self._execute_step(sealing_step)

            # Phase 6: Validation
            self._emit("phase_change", {"phase": "validation", "message": "Running post-configuration validation checks..."})
            validation = self._validate_deployment(environment)
            self._emit("validation_update", {"validation": validation})

            next_steps = [
                "1. Disconnect SSH session from the target VM.",
                "2. In CloudStack UI, perform a clean Shutdown of the VM.",
                "3. Navigate to Storage > Volumes and select the VM Root Volume.",
                "4. Click 'Create Template', enter template name, select OS type, enable Password and Dynamic Scaling.",
                f"5. Test launching a new VM from the template using default user '{self.cloudstack_user}'."
            ]

            result = {
                "status": "completed",
                "environment": environment.to_dict(),
                "cloudstack_username": self.cloudstack_user,
                "validation": validation,
                "execution_log": self.execution_log,
                "next_steps": next_steps
            }

            self._emit("execution_complete", {"status": "completed", "result": result})
            return result

        except Exception as e:
            self.logger.error(f"Template creation workflow failed: {e}", exc_info=True)
            err_msg = str(e)
            self._emit("execution_complete", {"status": "failed", "error": err_msg})
            return {
                "status": "failed",
                "error": err_msg,
                "execution_log": self.execution_log
            }
        finally:
            self.ssh.disconnect()

    def _execute_step(self, step: ExecutionStep):
        """Execute a single pipeline step with real-time event updates"""
        step_dict = {
            "name": step.name,
            "description": step.description,
            "command": step.command,
            "status": "running",
            "timestamp": datetime.utcnow().isoformat()
        }
        self._emit("step_update", {"step": step_dict})

        try:
            output = self.ssh.execute(step.command, sudo=True)
            step_dict["status"] = "completed"
            step_dict["output"] = output[:1500] if output else "Executed successfully."
            self.execution_log.append(step_dict)
            self._emit("step_update", {"step": step_dict})
        except Exception as e:
            step_dict["status"] = "failed"
            step_dict["error"] = str(e)
            self.execution_log.append(step_dict)
            self._emit("step_update", {"step": step_dict})
            if step.critical:
                raise

    def _deploy_config_files(self, generator: ScriptGenerator):
        """Write cloud-init configuration files securely"""
        configs = generator.generate_cloud_init_configs()
        for filepath, content in configs:
            try:
                parent_dir = str(Path(filepath).parent)
                self.ssh.execute(f"mkdir -p {parent_dir}", sudo=True)
                escaped = content.replace("'", "'\\''")
                cmd = f"echo '{escaped}' | tee {filepath} > /dev/null"
                self.ssh.execute(cmd, sudo=True)
                step_record = {
                    "name": f"Deploy Config: {Path(filepath).name}",
                    "description": f"Write {filepath}",
                    "status": "completed",
                    "output": f"Successfully created {filepath}",
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.execution_log.append(step_record)
                self._emit("step_update", {"step": step_record})
            except Exception as e:
                self.logger.error(f"Failed to write config {filepath}: {e}")
                raise

    def _validate_deployment(self, env: EnvironmentInfo) -> Dict[str, bool]:
        """Validate critical configuration targets on target VM"""
        checks = {}

        # 1. Cloud-init config files existence
        required_configs = [
            "/etc/cloud/cloud.cfg.d/99_cloudstack.cfg",
            "/etc/cloud/cloud.cfg.d/80_user.cfg",
            "/etc/cloud/cloud.cfg.d/49_hostkeys.cfg"
        ]
        for cfg in required_configs:
            name = Path(cfg).name
            try:
                res = self.ssh.execute(f"test -f {cfg} && echo 'OK' || echo 'MISSING'", sudo=True).strip()
                checks[f"{name}_exists"] = ("OK" in res)
            except Exception:
                checks[f"{name}_exists"] = False

        # 2. Cloud-init status
        try:
            status_output = self.ssh.execute("cloud-init --version 2>/dev/null", sudo=True).strip()
            checks["cloud_init_installed"] = bool(status_output)
        except Exception:
            checks["cloud_init_installed"] = False

        # 3. Machine ID sanitized
        try:
            m_id = self.ssh.execute("cat /etc/machine-id 2>/dev/null", sudo=True).strip()
            checks["machine_id_sanitized"] = (len(m_id) == 0)
        except Exception:
            checks["machine_id_sanitized"] = False

        # 4. Hostkeys cleaned
        try:
            hk_count = self.ssh.execute("ls -1 /etc/ssh/ssh_host_* 2>/dev/null | wc -l", sudo=True).strip()
            checks["ssh_hostkeys_cleaned"] = (hk_count == "0" or hk_count == "")
        except Exception:
            checks["ssh_hostkeys_cleaned"] = False

        return checks


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CloudStack Template Builder CLI")
    parser.add_argument("--host", required=True, help="SSH Host/IP")
    parser.add_argument("--user", default="root", help="SSH Username")
    parser.add_argument("--password", required=True, help="SSH Password")
    parser.add_argument("--cs-user", default="centos", help="CloudStack Default User")
    args = parser.parse_args()

    builder = TemplateBuilder(
        ssh_host=args.host,
        ssh_user=args.user,
        ssh_pass=args.password,
        cloudstack_user=args.cs_user,
        event_callback=lambda evt: print(f"[{evt.get('type')}] {json.dumps(evt, default=str)}")
    )
    res = builder.build()
    print("\nResult:", json.dumps(res, indent=2, default=str))
