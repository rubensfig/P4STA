# Copyright 2019-present Ralf Kundel, Fridolin Siegmund
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import copy
import json
import numpy as np
import os
import re
import subprocess
import sys
import threading
import time
import traceback

from abstract_loadgenerator import AbstractLoadgenerator

import P4STA_utils

dir_path = os.path.dirname(os.path.realpath(__file__))


class LoadGeneratorImpl(AbstractLoadgenerator):
    def __init__(self, loadgen_cfg):
        super().__init__(loadgen_cfg)
        self.directory = os.path.dirname(os.path.realpath(__file__))

    def get_name(self):
        return "trex"

    def run_loadgens(self, file_id, duration, l4_selected, packet_size_mtu,
                     results_path, loadgen_rate_limit, loadgen_flows,
                     loadgen_server_groups):
        self.cfg = P4STA_utils.read_current_cfg()
        loadgen_flows = int(loadgen_flows)
        print(loadgen_flows)
        host_ip = None
        host_user = None

        for loadgen_grp in self.cfg["loadgen_groups"]:
            answer = P4STA_utils.execute_ssh(loadgen_grp['loadgens']["ssh_user"], loadgen_grp['loadgens']["ssh_ip"],
                                             "systemctl status trex-server")


    # reads the iperf3 results and combine them into one result and into graphs
    def process_loadgen_data(self, file_id, results_path):
        min_rtt_list = []
        max_rtt_list = []
        total_interval_mbits = []
        total_interval_rtt = []
        total_interval_pl = []  # pl => packetloss
        total_interval_packets = []

        jsons = []
        for elem in next(os.walk(results_path))[2]:
            if elem.find(file_id) > 0 and elem.startswith("iperf3"):
                jsons.append(elem)

        jsons_dicts = []
        # to compare later if every interval has the same length
        total_intervals = 0
        l4_type = ""
        for js in jsons:
            print("joined path")
            print(os.path.join(results_path, js))
            l4_type, json_dict = self.read_iperf_json(
                os.path.join(results_path, js), file_id)
            jsons_dicts.append(json_dict)
        lowest_mbit_len = -1
        for json_dict in jsons_dicts:
            if len(json_dict["interval_mbits"]) < lowest_mbit_len \
                    or lowest_mbit_len == -1:
                lowest_mbit_len = len(json_dict["interval_mbits"])
        for json_dict in jsons_dicts:
            json_dict["interval_mbits"] = json_dict["interval_mbits"][
                                          0:lowest_mbit_len]
        for json_dict in jsons_dicts:
            if l4_type == "tcp":
                min_rtt_list.append(json_dict["s_min_rtt"])
                max_rtt_list.append(json_dict["s_max_rtt"])
            total_intervals = total_intervals + len(
                json_dict["interval_mbits"])

        to_plot = {"mbits": {}, "packetloss": {}}
        # if all intervals have same length it is compareable
        if len(jsons) > 0 and (total_intervals / len(jsons)) == len(
                jsons_dicts[0]["interval_mbits"]):
            for i in range(0, len(jsons_dicts[0]["interval_mbits"])):
                current_interval_mbits = current_interval_rtt = \
                    current_interval_pl = current_interval_packets = 0

                for js in jsons_dicts:
                    current_interval_mbits = current_interval_mbits + \
                                             js["interval_mbits"][i]
                    current_interval_pl = current_interval_pl + \
                        js["intervall_pl"][i]
                    if l4_type == "tcp":
                        current_interval_rtt = current_interval_rtt + \
                                               js["interval_rtt"][i]
                    else:
                        current_interval_packets = current_interval_packets + \
                                                   js["interval_packets"][i]

                total_interval_mbits.append(round(current_interval_mbits, 2))
                total_interval_pl.append(round(current_interval_pl, 2))
                if l4_type == "tcp":
                    total_interval_rtt.append(round(current_interval_rtt, 2))
                else:
                    total_interval_packets.append(
                        round(current_interval_packets, 2))

            if len(total_interval_mbits) > 0 and len(
                    total_interval_pl) > 0 and ((l4_type == "tcp" and len(
                    total_interval_rtt) > 0) or l4_type == "udp"):

                to_plot["mbits"] = {"value_list_input": total_interval_mbits,
                                    "index_list": np.arange(
                                        len(total_interval_mbits)),
                                    "titel": "iPerf3 " + l4_type.upper() +
                                             " throughput for all streams",
                                    "x_label": "t[s]",
                                    "y_label": "Speed [Mbit/s]",
                                    "filename": "loadgen_1",
                                    "adjust_unit": False, "adjust_y_ax": True}
                to_plot["packetloss"] = {"value_list_input": total_interval_pl,
                                         "index_list": np.arange(
                                             len(total_interval_pl)),
                                         "titel": "iPerf3 " + l4_type.upper()
                                                  + " retransmits for "
                                                    "all streams",
                                         "x_label": "t[s]",
                                         "y_label": "Retransmits [packets]",
                                         "filename": "loadgen_2",
                                         "adjust_unit": False,
                                         "adjust_y_ax": True}
                if l4_type == "tcp":
                    to_plot["rtt"] = {"value_list_input": total_interval_rtt,
                                      "index_list": np.arange(
                                          len(total_interval_rtt)),
                                      "titel": "iPerf3 " + l4_type.upper() +
                                               " average Round-Trip-Time for"
                                               " all streams",
                                      "x_label": "t[s]",
                                      "y_label": "RTT [microseconds]",
                                      "filename": "loadgen_3",
                                      "adjust_unit": False,
                                      "adjust_y_ax": True}
                else:
                    to_plot["packets"] = {
                        "value_list_input": total_interval_packets,
                        "index_list": np.arange(len(total_interval_packets)),
                        "titel":
                            "iPerf3 UDP packets per second for all streams",
                        "x_label": "t[s]", "y_label": "[packets/s]",
                        "filename": "loadgen_3", "adjust_unit": False,
                        "adjust_y_ax": True}
        else:
            to_plot = self.empty_plot()

        error = False
        # check if some iperf instance measured 0 bits -> not good
        if len(["s_bits" for elem in jsons_dicts if elem == 0]) == 0:
            total_bits = total_byte = total_retransmits = total_mean_rtt = \
                total_jitter = total_packets = total_lost = 0
            for js in jsons_dicts:
                total_bits = total_bits + js["s_bits"]
                total_byte = total_byte + js["s_byte"]
                if l4_type == "tcp":
                    total_retransmits = total_retransmits + js["s_retransmits"]
                    total_mean_rtt = total_mean_rtt + js["s_mean_rtt"]
                else:
                    total_jitter = total_jitter + js["s_jitter_ms"]
                    total_packets = total_packets + js["total_packets"]
                    total_lost = total_lost + js["total_lost"]

            if l4_type == "tcp":
                mean_rtt = round((total_mean_rtt / len(jsons)), 2)
                min_rtt = min(min_rtt_list)
                max_rtt = max(max_rtt_list)
            else:
                if len(jsons) > 0:
                    average_jitter_ms = round(total_jitter / len(jsons_dicts),
                                              2)
                else:
                    average_jitter_ms = 0

            output = [""]
        else:
            print("A iPerf3 instance measured 0 bits. Abort processing.")
            total_bits = total_byte = -1
            average_jitter_ms = total_packets = total_lost = -1
            total_retransmits = "error"
            mean_rtt = min_rtt = max_rtt = "error"
            output = ["error" for elem in jsons_dicts]
            error = True

        if l4_type == "tcp":
            custom_attr = \
                {"l4_type": l4_type, "elems": {
                    "mean_rtt": "Mean RTT: " + str(mean_rtt) + " microseconds",
                    "min_rtt": "Min RTT: " + str(min_rtt) + " microseconds",
                    "max_rtt": "Max RTT: " + str(max_rtt) + " microseconds"}}
        else:
            custom_attr = {"l4_type": l4_type, "elems": {
                "average_jitter_ms": "Jitter: " + str(
                    average_jitter_ms) + " milliseconds",
                "total_packets": "Total packets: " + str(
                    total_packets) + " packets/s",
                "total_lost": "Total Packetloss: " + str(
                    total_lost) + " packets"}}

        return output, total_bits, error, str(
            total_retransmits), total_byte, custom_attr, to_plot

    # reads iperf3 json into python variables
    def read_iperf_json(self, file_path, id):
        s_bits = s_byte = s_retransmits = s_mean_rtt = \
            s_min_rtt = s_max_rtt = -1
        interval_mbits = []
        interval_rtt = []
        intervall_pl = []  # pl=packetloss

        with open(file_path, "r") as s_json:
            s = json.load(s_json)

        l4_type = s["start"]["test_start"]["protocol"].lower()
        if l4_type == "tcp":
            try:
                s_bits = int(s["end"]["streams"][0]["sender"][
                                 "bits_per_second"])  # bits/second
                s_byte = int(s["end"]["streams"][0]["sender"][
                                 "bytes"])  # bytes total transfered
                s_retransmits = s["end"]["streams"][0]["sender"]["retransmits"]
                s_mean_rtt = int(s["end"]["streams"][0]["sender"]["mean_rtt"])
                s_min_rtt = int(s["end"]["streams"][0]["sender"]["min_rtt"])
                s_max_rtt = int(s["end"]["streams"][0]["sender"]["max_rtt"])
                for i in list(s["intervals"]):
                    if i["sum"]["seconds"] > 0.5:
                        # from bits to megabits
                        interval_mbits.append(i["streams"][0][
                                                  "bits_per_second"] / 1000000)
                        interval_rtt.append(i["streams"][0]["rtt"])
                        intervall_pl.append(i["streams"][0]["retransmits"])
                error = ""
            except Exception:
                print(traceback.format_exc())
                try:
                    error = s["error"]
                except Exception:
                    error = "Not able to find error report in " + file_path

            iperf_json = {"s_bits": s_bits, "s_byte": s_byte,
                          "s_retransmits": s_retransmits,
                          "s_mean_rtt": s_mean_rtt, "s_min_rtt": s_min_rtt,
                          "name": id,
                          "s_max_rtt": s_max_rtt, "error": error,
                          "interval_mbits": interval_mbits,
                          "interval_rtt": interval_rtt,
                          "intervall_pl": intervall_pl}

        else:
            interval_packets = []
            try:
                s_bits = int(s["end"]["sum"]["bits_per_second"])  # bits/second
                s_byte = int(
                    s["end"]["sum"]["bytes"])  # bytes total transfered
                s_jitter_ms = s["end"]["sum"]["jitter_ms"]
                total_packets = s["end"]["sum"]["packets"]
                total_lost = s["end"]["sum"]["lost_packets"]
                if total_packets != 0:
                    packetloss = total_lost / total_packets
                else:
                    packetloss = 0

                for i in list(s["intervals"]):
                    # from bits to megabits
                    interval_mbits.append(i["streams"][0][
                                              "bits_per_second"] / 1000000)
                    interval_packets.append(i["sum"]["packets"])
                    intervall_pl.append(packetloss / len(list(s["intervals"])))
                    # udp does not support intervall packet loss
                    # -> even distribution

                error = ""
            except Exception:
                print(traceback.format_exc())
                s_bits = s_byte = 0
                interval_mbits = intervall_pl = [0]
                try:
                    error = s["error"]
                except Exception:
                    error = "Not able to find error report in " + file_path

            iperf_json = {"s_bits": s_bits, "s_byte": s_byte,
                          "s_jitter_ms": s_jitter_ms,
                          "total_packets": total_packets, "name": file_path,
                          "total_lost": total_lost, "error": error,
                          "interval_mbits": interval_mbits,
                          "interval_packets": interval_packets,
                          "intervall_pl": intervall_pl}

        return l4_type, iperf_json

    def get_server_install_script(self, list_of_server):
        return ""

    def loadgen_status_overview(self, host, results, index):
        super(loadgeneratorimpl, self).loadgen_status_overview(host, results,
                                                               index)
        answer = P4STA_utils.execute_ssh(host["ssh_user"], host["ssh_ip"],
                                         "systemctl status trex-server")
        version = ""
        print(answer)
