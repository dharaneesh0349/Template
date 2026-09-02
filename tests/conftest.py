import pytest
from unittest.mock import MagicMock
from cloudstack_automation_implementation import (
    Distribution, PackageManager, Hypervisor, Filesystem,
    EnvironmentInfo, Disk, LVMInfo, SSHConnector
)

@pytest.fixture
def mock_ssh_rocky():
    mock = MagicMock(spec=SSHConnector)
    mock.host = "192.168.1.100"
    mock.port = 22

    def side_effect(cmd, *args, **kwargs):
        if "os-release" in cmd:
            return 'ID="rocky"\nVERSION_ID="9.2"\nID_LIKE="rhel centos fedora"'
        elif "systemd-detect-virt" in cmd or "dmidecode" in cmd:
            return "kvm\nQEMU\nStandard PC"
        elif "package_manager" in cmd or "which dnf" in cmd or "command -v dnf" in cmd:
            return "dnf"
        elif "lsblk" in cmd:
            return '''{
                "blockdevices": [
                    {
                        "name": "vda",
                        "size": "20G",
                        "type": "disk",
                        "mountpoint": null,
                        "children": [
                            {"name": "vda1", "size": "1G", "type": "part", "mountpoint": "/boot"},
                            {"name": "vda2", "size": "19G", "type": "part", "mountpoint": "/"}
                        ]
                    }
                ]
            }'''
        elif "lvdisplay" in cmd:
            return ""
        elif "pvdisplay" in cmd:
            return ""
        elif "df -hT" in cmd:
            return "TARGET FSTYPE\n/ xfs\n/boot ext4"
        elif "cloud-init" in cmd:
            return "cloud-init 23.1.2"
        elif "uname -r" in cmd:
            return "5.14.0-284.11.1.el9_2.x86_64"
        elif "ip -o -4" in cmd:
            return "192.168.1.100"
        elif "test -f" in cmd:
            return "OK"
        elif "cat /etc/machine-id" in cmd:
            return ""
        elif "ls -1 /etc/ssh/ssh_host_" in cmd:
            return "0"
        return "OK"

    mock.execute.side_effect = side_effect
    return mock


@pytest.fixture
def mock_ssh_ubuntu_lvm():
    mock = MagicMock(spec=SSHConnector)
    mock.host = "192.168.1.150"
    mock.port = 22

    def side_effect(cmd, *args, **kwargs):
        if "os-release" in cmd:
            return 'ID=ubuntu\nVERSION_ID="22.04"\nID_LIKE=debian'
        elif "systemd-detect-virt" in cmd:
            return "vmware"
        elif "package_manager" in cmd or "which apt" in cmd or "command -v" in cmd or "apt" in cmd:
            return "apt-get"
        elif "lsblk" in cmd:
            return '''{
                "blockdevices": [
                    {
                        "name": "sda",
                        "size": "40G",
                        "type": "disk",
                        "mountpoint": null,
                        "children": [
                            {"name": "sda1", "size": "1G", "type": "part", "mountpoint": "/boot"},
                            {"name": "sda2", "size": "39G", "type": "part", "mountpoint": null, "children": [
                                {"name": "ubuntu--vg-ubuntu--lv", "size": "39G", "type": "lvm", "mountpoint": "/"}
                            ]}
                        ]
                    }
                ]
            }'''
        elif "lvdisplay" in cmd:
            return "/dev/ubuntu-vg/ubuntu-lv:ubuntu-vg:3:1:-1:1:81788928:10223"
        elif "pvdisplay" in cmd:
            return "/dev/sda2:ubuntu-vg:41940992:-1:1:1:-1:4096:10239:10239:0"
        elif "df -hT" in cmd:
            return "TARGET FSTYPE\n/ ext4\n/boot ext4"
        elif "cloud-init" in cmd:
            return "cloud-init 22.2-0ubuntu1~22.04.3"
        elif "uname -r" in cmd:
            return "5.15.0-76-generic"
        elif "ip -o -4" in cmd:
            return "192.168.1.150"
        return "OK"

    mock.execute.side_effect = side_effect
    return mock
