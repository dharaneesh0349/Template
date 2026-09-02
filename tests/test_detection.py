from cloudstack_automation_implementation import (
    EnvironmentDetector, Distribution, PackageManager, Hypervisor, Filesystem
)

def test_detect_rocky_kvm(mock_ssh_rocky):
    detector = EnvironmentDetector(mock_ssh_rocky)
    env = detector.detect_all()

    assert env.distribution == Distribution.ROCKY
    assert env.version == "9.2"
    assert env.package_manager == PackageManager.DNF
    assert env.hypervisor == Hypervisor.KVM
    assert env.filesystem_type == Filesystem.XFS
    assert env.root_partition == "/dev/vda2"
    assert env.cloud_init_installed is True
    assert "23.1.2" in env.cloud_init_version


def test_detect_ubuntu_lvm(mock_ssh_ubuntu_lvm):
    detector = EnvironmentDetector(mock_ssh_ubuntu_lvm)
    env = detector.detect_all()

    assert env.distribution == Distribution.UBUNTU
    assert env.version == "22.04"
    assert env.package_manager in [PackageManager.APT_GET, PackageManager.APT]
    assert env.hypervisor == Hypervisor.VMWARE
    assert env.filesystem_type == Filesystem.EXT4
    assert env.root_lv is not None
    assert env.root_lv.vg_name == "ubuntu-vg"
    assert env.root_lv.pv_path == "/dev/sda2"
