import multiprocessing
import logging
import os
import urllib.request
import json
import time
import psutil
import boto3
import requests



CONTAINERS_URL = os.getenv('CONTAINERS_URL', 'http://localhost:5051/containers')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger()


def autoscaling_connection():
    """Boto3 connection to EC2 for autoscaling"""
    client = boto3.client('autoscaling', region_name=get_instance_region())
    return client

def cloudwatch_connection():
    """Boto3 connection to EC2 for cloudwatch"""
    client = boto3.client('cloudwatch', region_name=get_instance_region())
    return client

def get_instance_id():
    instanceid = urllib.request.urlopen('http://169.254.169.254/latest/meta-data/instance-id').read().decode()
    return instanceid

def get_instance_region():
    document = json.loads(urllib.request.urlopen('http://169.254.169.254/latest/dynamic/instance-identity/document').read().decode())
    return document['region']

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


    return memory_used_percentage, cpu_used_percentage

def collect_memory_total():
    total_memory = psutil.virtual_memory().total
    logging.info("Detected %s bytes total memory", total_memory)
    return total_memory


def get_autoscaling_group(instance_id):
    """Gets autoscaling group details"""
    client = autoscaling_connection()
    response = client.describe_auto_scaling_instances(InstanceIds=[instance_id])
    return response['AutoScalingInstances'][0]['AutoScalingGroupName']


def send_multi_metrics(mem_usage, cpu_usage, asg_name,
                       namespace='EC2/Memory'):
    metric_data = [
        {
            'MetricName': 'MemReservationUsage',
            'Dimensions': [
                {
                    'Name': 'AutoScalingGroupName',
                    'Value': asg_name
                }
            ],
            'Timestamp': int(time.time()),
            'Value': mem_usage,
            'Unit': 'Percent'
        },
        {
            'MetricName': 'CPUReservationUsage',
            'Dimensions': [
                {
                    'Name': 'AutoScalingGroupName',
                    'Value': asg_name
                }
            ],
            'Timestamp': int(time.time()),
            'Value': cpu_usage,
            'Unit': 'Percent'
        }
    ]

    cloud_watch = cloudwatch_connection()
    response = cloud_watch.put_metric_data(Namespace=namespace, MetricData=metric_data)
    logging.info("Sent the following metrics: %s to cloudwatch", metric_data)
    if response['ResponseMetadata']['HTTPStatusCode'] is not 200:
        return False
    return True


mem_used, cpu_used = get_used_percentages(CONTAINERS_URL)

send_multi_metrics(mem_used, cpu_used, get_autoscaling_group(get_instance_id()))
