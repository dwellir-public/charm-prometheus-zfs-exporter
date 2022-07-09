#!/usr/bin/env python3
# Copyright 2021 Omnivector Solutions.
# See LICENSE file for licensing details.

"""Prometheus Node Exporter Charm."""

import logging
import os
import re
import shlex
import shutil
import subprocess
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib import request
import subprocess as sp
from jinja2 import Environment, FileSystemLoader

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus

from prometheus_zfs_exporter import Prometheus

logger = logging.getLogger(__name__)


class ZfsExporterCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        """Initialize charm."""
        super().__init__(*args)

        self.prometheus = Prometheus(self, "prometheus")

        # juju core hooks
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)

    @property
    def port(self):
        """Return the port that node-exporter listens to."""
        return self.model.config.get("listen-address").split(":")[1]

    def _on_install(self, event):
        logger.debug("## Installing charm")
        self.unit.status = MaintenanceStatus("Installing zfs-exporter")
        self._set_charm_version()
        _install_node_exporter(self.model.config.get("zfs-exporter-version"))

        self.unit.status = ActiveStatus("zfs-exporter installed")

    def _on_upgrade_charm(self, event):
        """Perform upgrade operations."""
        logger.debug("## Upgrading charm")
        self.unit.status = MaintenanceStatus("Upgrading zfs-exporter")
        self._set_charm_version()

        self.unit.status = ActiveStatus("zfs-exporter upgraded")

    def _on_config_changed(self, event):
        """Handle configuration updates."""
        logger.debug("## Configuring charm")

        params = dict()
        params["listen_address"] = self.model.config.get("listen-address")

        logger.debug(f"## Configuration options: {params}")
        _render_sysconfig(params)
        subprocess.call(["systemctl", "restart", "zfs_exporter"])

        self.prometheus.set_host_port()

    def _on_start(self, event):
        logger.debug("## Starting daemon")
        subprocess.call(["systemctl", "start", "zfs_exporter"])
        self.unit.status = ActiveStatus("zfs-exporter started")

    def _on_stop(self, event):
        logger.debug("## Stopping daemon")
        subprocess.call(["systemctl", "stop", "zfs_exporter"])
        subprocess.call(["systemctl", "disable", "zfs_exporter"])
        _uninstall_node_exporter()

    def _set_charm_version(self):
        """Set the application version for Juju Status."""
        command = ['/usr/bin/zfs_exporter', '--version']
        output = sp.run(command, capture_output=True, text=True).stderr
        version = re.search(r'([0-9]+.[0-9]+.[0-9]+)', output).group(0)
        self.unit.set_workload_version(version)


def _install_node_exporter(version: str, arch: str = "amd64"):
    """Download appropriate files and install node-exporter.

    This function downloads the package, extracts it to /usr/bin/, create
    node-exporter user and group, and creates the systemd service unit.

    Args:
        version: a string representing the version to install.
        arch: the hardware architecture (e.g. amd64, armv7).
    """

    logger.debug(f"## Installing node_exporter {version}")

    # Download file
    url = f"https://github.com/pdf/zfs_exporter/releases/download/v{version}/zfs_exporter-{version}.linux-{arch}.tar.gz"
    logger.debug(f"## Downloading {url}")
    output = Path("/tmp/zfs-exporter.tar.gz")
    fname, headers = request.urlretrieve(url, output)

    # Extract it
    tar = tarfile.open(output, 'r')
    with TemporaryDirectory(prefix="charmtmp") as tmp_dir:
        logger.debug(f"## Extracting {tar} to {tmp_dir}")
        tar.extractall(path=tmp_dir)

        logger.debug("## Installing zfs_exporter")
        source = Path(tmp_dir) / f"zfs_exporter-{version}.linux-{arch}/zfs_exporter"
        shutil.copy2(source, "/usr/bin/zfs_exporter")

    # clean up
    output.unlink()

    _create_node_exporter_user_group()
    _create_systemd_service_unit()
    la = str(self.config.get('listen-address'))
    _render_sysconfig({"listen_address": la})


def _uninstall_node_exporter():
    logger.debug("## Uninstalling zfs-exporter")

    # remove files and folders
    Path("/usr/bin/zfs_exporter").unlink()
    Path("/etc/systemd/system/zfs_exporter.service").unlink()
    Path("/etc/sysconfig/zfs_exporter").unlink()
    shutil.rmtree(Path("/var/lib/zfs_exporter/"))

    # remove user and group
    user = "zfs_exporter"
    group = "zfs_exporter"
    subprocess.call(["userdel", user])
    subprocess.call(["groupdel", group])


def _create_node_exporter_user_group():
    logger.debug("## Creating zfs_exporter group")
    group = "zfs_exporter"
    cmd = f"groupadd {group}"
    subprocess.call(shlex.split(cmd))

    logger.debug("## Creating zfs_exporter user")
    user = "zfs_exporter"
    cmd = f"useradd --system --no-create-home --gid {group} --shell /usr/sbin/nologin {user}"
    subprocess.call(shlex.split(cmd))


def _create_systemd_service_unit():
    logger.debug("## Creating systemd service unit for zfs_exporter")
    charm_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = Path(charm_dir) / "templates"

    service = "zfs_exporter.service"
    shutil.copyfile(template_dir / service, f"/etc/systemd/system/{service}")

    subprocess.call(["systemctl", "daemon-reload"])
    subprocess.call(["systemctl", "enable", service])


def _render_sysconfig(context: dict) -> None:
    """Render the sysconfig file.

    `context` should contain the following keys:
        listen_address: a string specifiyng the address to listen to, e.g. 0.0.0.0:9134
    """
    logger.debug("## Writing sysconfig file")

    charm_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = Path(charm_dir) / "templates"
    template_file = "zfs_exporter.tmpl"

    sysconfig = Path("/etc/sysconfig/")
    if not sysconfig.exists():
        sysconfig.mkdir()

    varlib = Path("/var/lib/zfs_exporter")
    textfile_dir = varlib / "textfile_collector"
    if not textfile_dir.exists():
        textfile_dir.mkdir(parents=True)
    shutil.chown(varlib, user="zfs_exporter", group="zfs_exporter")
    shutil.chown(textfile_dir, user="zfs_exporter", group="zfs_exporter")

    environment = Environment(loader=FileSystemLoader(template_dir))
    template = environment.get_template(template_file)

    target = sysconfig / "zfs_exporter"
    if target.exists():
        target.unlink()
    target.write_text(template.render(context))


if __name__ == "__main__":
    main(ZfsExporterCharm)
