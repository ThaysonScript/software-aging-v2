import threading
import time
from datetime import datetime

from src.utils import execute_command, write_to_file, get_time


class MonitoringEnvironment:
    def __init__(
            self,
            path: str,
            sleep_time: int,
            software: str,
            containers: list,
            sleep_time_container_metrics: int,
            old_software: str,
            old_system: str,
            system: str,
    ):
        log_dir = software
        if old_software:
            log_dir = log_dir + "_old_"
        else:
            log_dir = log_dir + "_new_"

        log_dir = log_dir + system
        if old_system:
            log_dir = log_dir + "_old"
        else:
            log_dir = log_dir + "_new"
        self.path = path
        self.log_dir = log_dir
        self.sleep_time = sleep_time
        self.software = software
        self.containers = containers
        self.sleep_time_container_metrics = sleep_time_container_metrics

    def start(self):
        print("Starting monitoring scripts")
        self.start_systemtap()
        self.start_container_lifecycle_monitoring()
        self.start_machine_resources_monitoring()

    def start_machine_resources_monitoring(self):
        monitoring_thread = threading.Thread(target=self.machine_resources, name="monitoring")
        monitoring_thread.daemon = True
        monitoring_thread.start()

    def start_container_lifecycle_monitoring(self):
        container_metrics_thread = threading.Thread(target=self.container_metrics, name="container_metrics")
        container_metrics_thread.daemon = True
        container_metrics_thread.start()

    def start_systemtap(self):
        def systemtap():
            command = f"stap -o {self.path}/{self.log_dir}/fragmentation.csv {self.path}/fragmentation.stp"
            execute_command(command)

        monitoring_thread = threading.Thread(target=systemtap, name="systemtap")
        monitoring_thread.daemon = True
        monitoring_thread.start()

    def container_lifecycle(self):
        for container in self.containers:
            container_name = container["name"]
            host_port = container["host_port"]
            container_port = container["port"]

            load_image_time = get_time(f"{self.software} load -i {self.path}/{container_name}.tar -q")

            start_time = get_time(
                f"{self.software} run --name {container_name} -td -p {host_port}:{container_port} --init {container_name}")

            up_time = execute_command(
                f"{self.software} exec -i {container_name} sh -c \"test -e /root/log.txt && cat /root/log.txt\"",
                continue_if_error=True, error_informative=False)

            while up_time is None:
                up_time = execute_command(
                    f"{self.software} exec -i {container_name} sh -c \"test -e /root/log.txt && cat /root/log.txt\"",
                    continue_if_error=True, error_informative=False)

            stop_time = get_time(f"{self.software} stop {container_name}")

            remove_container_time = get_time(f"{self.software} rm {container_name}")

            remove_image_time = get_time(f"{self.software} rmi {container_name}")

            write_to_file(
                f"{self.path}/{self.log_dir}/{container_name}.csv",
                "load_image;start;up_time;stop;remove_container;remove_image",
                f"{load_image_time};{start_time};{up_time};{stop_time};{remove_container_time};{remove_image_time}"
            )

    def machine_resources(self):
        while True:
            now = datetime.now()
            date_time = now.strftime("%Y-%m-%d %H:%M:%S")
            self.cpu_monitoring(date_time)
            self.disk_monitoring(date_time)
            self.memory_monitoring(date_time)
            self.process_monitoring(date_time)
            time.sleep(self.sleep_time)

    def container_metrics(self):
        while True:
            self.container_lifecycle()
            time.sleep(self.sleep_time_container_metrics)

    def disk_monitoring(self, date_time):
        comando = "df | grep '/$' | awk '{print $3}'"
        mem = execute_command(comando)

        write_to_file(
            f"{self.path}/{self.log_dir}/disk.csv",
            "used;time",
            f"{mem};{date_time}"
        )

    def cpu_monitoring(self, date_time):
        cpu_info = execute_command("mpstat | grep all").split()
        usr = cpu_info[2]
        nice = cpu_info[3]
        sys_used = cpu_info[4]
        iowait = cpu_info[5]
        soft = cpu_info[7]

        write_to_file(
            f"{self.path}/{self.log_dir}/cpu.csv",
            "usr;nice;sys;iowait;soft;time",
            f"{usr};{nice};{sys_used};{iowait};{soft};{date_time}"
        )

    def memory_monitoring(self, date_time):
        used = execute_command("free | grep Mem | awk '{print $3}'")
        cached = execute_command("cat /proc/meminfo | grep -i Cached | sed -n '1p' | awk '{print $2}'")
        buffers = execute_command("cat /proc/meminfo | grep -i Buffers | sed -n '1p' | awk '{print $2}'")
        swap = execute_command("cat /proc/meminfo | grep -i Swap | grep -i Free | awk '{print $2}'")

        write_to_file(
            f"{self.path}/{self.log_dir}/memory.csv",
            "used;cached;buffers;swap;time",
            f"{used};{cached};{buffers};{swap};{date_time}"
        )

    def process_monitoring(self, date_time):
        zombies = execute_command("ps aux | awk '{if ($8 ~ \"Z\") {print $0}}' | wc -l")

        write_to_file(
            f"{self.path}/{self.log_dir}/process.csv",
            "zombies;time",
            f"{zombies};{date_time}"
        )