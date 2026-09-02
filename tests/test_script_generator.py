import yaml
from cloudstack_automation_implementation import (
    ScriptGenerator, EnvironmentInfo, Distribution, PackageManager,
    Hypervisor, Filesystem, Disk, LVMInfo
)

def test_script_generator_rocky():
    env = EnvironmentInfo(
        distribution=Distribution.ROCKY,
        version="9.2",
        package_manager=PackageManager.DNF,
        hypervisor=Hypervisor.KVM,
        boot_partition="/dev/vda1",
        root_partition="/dev/vda2",
        root_lv=None,
        filesystem_type=Filesystem.XFS,
        root_mountpoint="/",
        all_disks=[],
        cloud_init_installed=True,
        cloud_init_version="23.1.2"
    )

    gen = ScriptGenerator(env, cloudstack_username="rocky")

    # Base config
    step1 = gen.generate_base_system_config()
    assert "dnf" in step1.command
    assert "hostnamectl" in step1.command

    # Cloud-init install
    step2 = gen.generate_cloud_init_install()
    assert "dnf install -y cloud-init" in step2.command

    # Guest agent
    step3 = gen.generate_guest_agent_install()
    assert "qemu-guest-agent" in step3.command

    # Config files
    configs = dict(gen.generate_cloud_init_configs())
    assert "/etc/cloud/cloud.cfg.d/99_cloudstack.cfg" in configs
    cloudstack_cfg = yaml.safe_load(configs["/etc/cloud/cloud.cfg.d/99_cloudstack.cfg"])
    assert "CloudStack" in cloudstack_cfg["datasource_list"]

    assert "/etc/cloud/cloud.cfg.d/80_user.cfg" in configs
    user_cfg = yaml.safe_load(configs["/etc/cloud/cloud.cfg.d/80_user.cfg"])
    assert user_cfg["system_info"]["default_user"]["name"] == "rocky"

    # Sealing
    seal = gen.generate_deep_sealing_script()
    assert "machine-id" in seal.command
    assert "ssh_host_" in seal.command


def test_script_generator_ubuntu_lvm():
    root_lv = LVMInfo(
        lv_path="/dev/ubuntu-vg/ubuntu-lv",
        vg_name="ubuntu-vg",
        pv_path="/dev/sda2",
        pv_size="40G"
    )
    env = EnvironmentInfo(
        distribution=Distribution.UBUNTU,
        version="22.04",
        package_manager=PackageManager.APT_GET,
        hypervisor=Hypervisor.VMWARE,
        boot_partition="/dev/sda1",
        root_partition="/dev/sda2",
        root_lv=root_lv,
        filesystem_type=Filesystem.EXT4,
        root_mountpoint="/",
        all_disks=[],
        cloud_init_installed=True,
        cloud_init_version="22.2"
    )

    gen = ScriptGenerator(env, cloudstack_username="ubuntu")

    # Cloud-init install
    step2 = gen.generate_cloud_init_install()
    assert "apt-get install -y cloud-init" in step2.command

    # Guest agent
    step3 = gen.generate_guest_agent_install()
    assert "open-vm-tools" in step3.command

    # Config files check for LVM expansion
    configs = dict(gen.generate_cloud_init_configs())
    assert "/etc/cloud/cloud.cfg.d/51_extend_volume.cfg" in configs
    lvm_cfg = yaml.safe_load(configs["/etc/cloud/cloud.cfg.d/51_extend_volume.cfg"])
    assert len(lvm_cfg["runcmd"]) >= 3
