import boto3
import os
from datetime import datetime, timedelta


# Variables
retention_days = 7

# Empty lists
volumes_list = []
snapshots_to_delete_list = []

# AWS config
profile = boto3.Session()
ec2 = boto3.client('ec2')
response = ec2.describe_instances()
snaposhots_response = ec2.describe_snapshots()

# Time variables
now = datetime.now()
datestring = now.strftime("%Y-%m-%d-%H-%M-%S")
deltatime = now - timedelta(days=retention_days)

# Functions
def get_name(instance):
    for r in response['Reservations']:
      for i in r['Instances']:
          if i['InstanceId'] == instance:
              for tag in i['Tags']:
                  if tag['Key'] == 'Name':
                      return tag['Value']

def get_volumes_list():
    for r in response['Reservations']:
      for i in r['Instances']:
        attrib =  ec2.describe_instance_attribute(Attribute='disableApiTermination', InstanceId=i['InstanceId'])
        if attrib["DisableApiTermination"]['Value'] is True:
            if i['State']['Name'] == "running":
                for b in i['BlockDeviceMappings']:
                    volumes_list.append(({'instance_id': i['InstanceId'], 'instance_name': get_name(i['InstanceId']) , 'device_name' : b['DeviceName'], 'volume_id' : b['Ebs'].get('VolumeId')}))

def create_snapshots():
    for volume in volumes_list:
        description = "Scheduled_Backup_" + volume['instance_name'] + "_" + volume['device_name'] + "_" + datestring
        print "creating snapshot " + description
        ec2.create_snapshot(
        Description=description,
        VolumeId=volume['volume_id'],
        TagSpecifications=[
            {
                'ResourceType': 'snapshot',
                'Tags': [
                    {
                        'Key': 'Purpose',
                        'Value': 'data-recovery'
                    },
                ]
            },
        ],
        DryRun=False
    )

def generate_snapshots_to_delete_list():
    for volume in volumes_list:
        for snapshot in snaposhots_response['Snapshots']:
            if 'Scheduled_Backup' in snapshot['Description']:
                if snapshot['VolumeId'] == volume['volume_id'] and snapshot['State'] == 'completed':
                    x = snapshot['StartTime'].date()
                    z = now.date() - x
                    if z.days  > retention_days:
                        snapshots_to_delete_list.append(snapshot['SnapshotId'])
                        #return snapshot['SnapshotId']

def delete_snapshots():
    for snapshot in snapshots_to_delete_list:
        print "deleting snapshot " + snapshot
        ec2.delete_snapshot(
            SnapshotId=snapshot,
            DryRun=False
        )

def handler(event, context):
    get_volumes_list()
    create_snapshots()
    generate_snapshots_to_delete_list()
    delete_snapshots()
