import requests
import multiprocessing
import psutil
import boto
import boto.ec2.autoscale
import boto.ec2
from boto.utils import get_instance_metadata
from boto.ec2 import cloudwatch
import logging
import os

CONTAINERS_URL = os.getenv('CONTAINERS_URL', 'http://localhost:5051/containers')

region = boto.ec2.regions()[6].name
metadata = get_instance_metadata()
instance_id = get_instance_metadata()['instance-id']

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger()


def get_processor_count():
    cpu_count = multiprocessing.cpu_count()
    logging.info("Detected %s processors", cpu_count)
    return cpu_count


def get_used_percentages(containers_url):
    total_cpu_limit = 0.0
    total_mem_limit = 0.0
    metrics = {}

    r = requests.get(containers_url)

    for container in r.json():
        total_cpu_limit += container['statistics']['cpus_limit']
        total_mem_limit += container['statistics']['mem_limit_bytes']

    cpu_used_percentage = (total_cpu_limit / get_processor_count()) * 100
    memory_used_percentage = (total_mem_limit / collect_memory_total()) * 100

    logging.info("Calculated used reservation CPU percentage at %s", cpu_used_percentage)
    logging.info("Calculated used reservation memory percentage at %s", memory_used_percentage)

    metrics = {'MemReservationUsage': memory_used_percentage,
               'CPUReservationUsage': cpu_used_percentage}
    return metrics


def collect_memory_total():
    total_memory = psutil.virtual_memory().total
    logging.info("Detected %s bytes total memory", total_memory)
    return total_memory


# Shamelessly stolen from Amit's script! :-)
def get_autoscale_group(instance_id):
    asg_name = ''
    instance_id = instance_id
    autoscale_connection = boto.ec2.autoscale.connect_to_region(region)

    asg_groups = autoscale_connection.get_all_groups()
    found_flag = False

    for grp in asg_groups:
        for instance in grp.instances:
            if instance_id == instance.instance_id:
                found_flag = True
                break
        if found_flag:
            for tag in grp.tags:
                if tag.key == 'Name':
                    asg_name = (tag.resource_id)
                    break
            break
    logging.info("This instance is part of %s autoscaling group", asg_name)

    return asg_name


def send_multi_metrics(instance_id, region, metrics, asg_name, namespace='EC2/Memory',
                       unit='Percent'):
    cloud_watch = cloudwatch.connect_to_region(region)
    cloud_watch.put_metric_data(namespace, metrics.keys(), metrics.values(),
                                unit=unit,
                                dimensions={"AutoScalingGroupName": asg_name})
    logging.info("Sent the following metrics: %s for instance_id: %s in asg: %s", metrics, instance_id, asg_name)


send_multi_metrics(instance_id, region, get_used_percentages(CONTAINERS_URL), get_autoscale_group(instance_id))
