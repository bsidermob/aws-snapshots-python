import boto3
import os
from datetime import datetime, timedelta
from dateutil.parser import *

# This creates AMIs from instances which have termination protection ON.
# It keeps them for X days and then cleans them up.
# It also adds tags to AMIs and their snapshots.
# And adds permissions to particular AMIs so they are shared with another
# AWS account. Sharing can't be done straight away until snapshot
# is finished so it's applied to pre-existing snapshots (which were
# created during previous runs of this script).
#
# Initially this script was creating just snapshots but then
# it was modified to create AMI images instead as it's more convenient
# for restore purposes.

# Variables
retention_days = 7
# this is AWS AU non-prod account ID
grant_access_to_aws_id = ""
grant_access_to_ami_name_mask = "ami-names-needed-to-be-granted-access-to"
tags_to_add = [{
        'Key': 'Purpose',
        'Value': 'data-recovery'
    },
    {
        'Key': 'Type',
        'Value': 'automated-backup'
}]

# Empty lists, dicts
volumes_list = []
instances_dict = []
snapshots_to_delete_list = []
amis_to_delete_list = []
created_amis_list = []

# AWS config
profile = boto3.Session()
ec2 = boto3.client('ec2')
response = ec2.describe_instances()
snaposhots_response = ec2.describe_snapshots()
images_response = ec2.describe_images(Owners=['self'])

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


def get_instances_list():
    # instances_list = []
    for r in response['Reservations']:
        for i in r['Instances']:
            attrib = ec2.describe_instance_attribute(Attribute='disableApiTermination', InstanceId=i['InstanceId'])
            if attrib["DisableApiTermination"]['Value'] is True:
                if i['State']['Name'] == "running":
                    instances_dict.append(
                        ({'instance_id': i['InstanceId'], 'instance_name': get_name(i['InstanceId'])}))


def get_volumes_list():
    # volumes_dict = []
    for r in response['Reservations']:
        for i in r['Instances']:
            attrib = ec2.describe_instance_attribute(Attribute='disableApiTermination', InstanceId=i['InstanceId'])
            if attrib["DisableApiTermination"]['Value'] is True:
                if i['State']['Name'] == "running":
                    for b in i['BlockDeviceMappings']:
                        volumes_list.append((
                            {'instance_id': i['InstanceId'], 'instance_name': get_name(i['InstanceId']),
                             'device_name': b['DeviceName'], 'volume_id': b['Ebs'].get('VolumeId')}))


def create_amis():
    for ami in instances_dict:
        description = "Scheduled_Backup_" + ami['instance_name'] + "_" + ami['instance_id'] + "_" + datestring
        name = ami['instance_name'] + "_" + datestring
        print "creating AMI " + description
        func_response = ec2.create_image(
            Description=description,
            DryRun=False,
            InstanceId=ami['instance_id'],
            Name=name,
            NoReboot=True
        )
        created_amis_list.append(func_response['ImageId'])

    # print created_amis_list
    # add tags to newly created AMIs
    for ami in created_amis_list:
        ec2.create_tags(
            DryRun=False,
            Resources=[
                ami,
            ],
            Tags=tags_to_add
        )
    # add tags to AMIs' volumes
    for ami in created_amis_list:
        func_response = ec2.describe_images(ImageIds=[ami])
        for snapshot in func_response['Images'][0]['BlockDeviceMappings']:
            try:
                snapshot_id = snapshot['Ebs']['SnapshotId']
                ec2.create_tags(
                    DryRun=False,
                    Resources=[
                        snapshot_id,
                    ],
                    Tags=tags_to_add
                )
            except:
                "Snapshot for " + ami + " not tagged"

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
                    'Tags': tags_to_add
                },
            ],
            DryRun=False
        )


def generate_amis_to_delete_list():
    for ami in instances_dict:
        for image in images_response['Images']:
            if 'Scheduled_Backup' in image['Description']:
                if ami['instance_id'] in image['Description'] and image['State'] == 'available':
                    x = parse(image['CreationDate']).date()
                    z = now.date() - x
                    if z.days > retention_days:
                        amis_to_delete_list.append(image['ImageId'])
                    # print image['ImageId']


def generate_snapshots_to_delete_list():
    for volume in volumes_list:
        for snapshot in snaposhots_response['Snapshots']:
            if 'Scheduled_Backup' in snapshot['Description'] and snapshot['VolumeId'] == volume['volume_id'] and \
                    snapshot['State'] == 'completed':
                x = snapshot['StartTime'].date()
                z = now.date() - x
                if z.days > retention_days:
                    snapshots_to_delete_list.append(snapshot['SnapshotId'])
    # delete snapshots which belong to AMIs
    for ami in amis_to_delete_list:
        func_response = ec2.describe_images(ImageIds=[ami])
        for snapshot in func_response['Images'][0]['BlockDeviceMappings']:
            if 'Ebs' in snapshot:
                snapshots_to_delete_list.append(snapshot['Ebs']['SnapshotId'])


def delete_snapshots():
    for snapshot in snapshots_to_delete_list:
        print "deleting snapshot " + snapshot
        ec2.delete_snapshot(
            SnapshotId=snapshot,
            DryRun=False
        )


def delete_amis():
    for ami in amis_to_delete_list:
        print "Deregistering AMI " + ami
        ec2.deregister_image(
            ImageId=ami,
            DryRun=False
        )


def add_ami_permissions():
    # add permissions for instance
    for ami in images_response['Images']:
        if grant_access_to_ami_name_mask in ami['Name']:
            image_id = ami['ImageId']
            try:
                ec2.modify_image_attribute(
                    Attribute='launchPermission',
                    ImageId=image_id,
                    LaunchPermission={
                        'Add': [
                            {
                                'UserId': grant_access_to_aws_id
                            }
                        ]
                    },
                    OperationType='add',
                    DryRun=False
                )
                print "Permissions for " + grant_access_to_aws_id + " account added to " + image_id
            except:
                print "Access to " + image_id + " can't be granted yet"


def handler(event, context):
    get_volumes_list()
    get_instances_list()
    #create_snapshots()
    create_amis()
    generate_amis_to_delete_list()
    generate_snapshots_to_delete_list()
    add_ami_permissions()
    delete_amis()
    delete_snapshots()
