#!/usr/bin/env python3

"""COS Proxy Charm Test."""

import json
import charm
import subprocess
import unittest
from ops.testing import Harness
from unittest.mock import patch


@patch.object(subprocess, "call", new=lambda *args, **kwargs: None)
class COSProxyCharmTest(unittest.TestCase):
    """Charm test."""

    def setUp(self):
        """Set the harness up."""
        self.harness = Harness(charm.ZfsExporterCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_prometheus_relation(self):
        """Check that the charm and prom are related."""
        charm = self.harness.charm
        prometheus = charm.prometheus

        # relation created evt
        with patch.object(prometheus, 'set_host_port') as mock:
            rel_id = self.harness.add_relation(
                prometheus._relation_name,
                'prometheus')
            key_values = {"ingress-address": "127.4.5.6"}
            self.harness.add_relation_unit(rel_id, "prometheus/1")
            self.harness.update_relation_data(
                rel_id,
                charm.unit.name,
                key_values
            )

        # verify that it would have been called
        mock.assert_called_once()
        # call it
        prometheus.set_host_port()

        # verify the databag contents
        rel_data = self.harness.get_relation_data(rel_id, charm.unit.name)
        assert rel_data == {
            'ingress-address': '127.4.5.6',
            'hostname': '127.4.5.6',
            'port': '9134',
            'metrics_path': '/metrics'
        }

    def test_metrics_endpoint_relation_publishes_topology_scrape_metadata(self):
        """The preferred prometheus_scrape relation should publish topology-aware data."""
        charm_instance = self.harness.charm
        self.harness.set_leader(True)
        rel_id = self.harness.add_relation("metrics-endpoint", "alloy")
        self.harness.add_relation_unit(rel_id, "alloy/0")

        rel_data_app = self.harness.get_relation_data(rel_id, charm_instance.app.name)
        rel_data_unit = self.harness.get_relation_data(rel_id, charm_instance.unit.name)

        scrape_metadata = json.loads(rel_data_app["scrape_metadata"])

        assert scrape_metadata["model"] == charm_instance.model.name
        assert scrape_metadata["application"] == charm_instance.app.name
        assert scrape_metadata["charm_name"] == charm_instance.meta.name
        assert rel_data_unit["prometheus_scrape_unit_address"]
        assert rel_data_unit["prometheus_scrape_unit_name"] == charm_instance.unit.name
        assert rel_data_unit.get("prometheus_scrape_unit_path", "") == ""
