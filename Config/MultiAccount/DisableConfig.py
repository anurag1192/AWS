#!/usr/bin/env python

import boto3
import sys
import time
import argparse
import re

from collections import OrderedDict
from botocore.exceptions import ClientError


def assume_role(aws_account_number, role_name):
    """
	Assumes the provided role in each account and returns a Config client
	:param aws_account_number: AWS Account Number
	:param role_name: Role to assume in target account
	:param aws_region: AWS Region for the Client call, not required for IAM calls
	:return: Config client in the specified AWS Account and Region
	"""

    # Beginning the assume role process for account
    sts_client = boto3.client('sts')

    # Get the current partition
    partition = sts_client.get_caller_identity()['Arn'].split(":")[1]

    response = sts_client.assume_role(RoleArn='arn:{}:iam::{}:role/{}'.format(
        partition, aws_account_number, role_name),
                                      RoleSessionName='EnableConfig')

    # Storing STS credentials
    session = boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken'])

    print('\033[1m' + "-----------------------------------------")
    print('\033[1m' +
          "||||Assumed session for {}||||".format(aws_account_number))
    print('\033[1m' + "-----------------------------------------")
    print('\033[0m')

    return session


def disable_config(config_client,account,aws_region):

    try:
        stop_configuration_recorder = config_client.stop_configuration_recorder(ConfigurationRecorderName="default")
        print("Stopped Configuration Recorder in {} region {} ✅".format(account, aws_region))
    except Exception as e:
        print("{} in {} region {} ❌".format(e,account,aws_region))
    try:
        delete_delivery_channel = config_client.delete_delivery_channel(DeliveryChannelName="default")
        print("Deleted Delivery Channel in {} region {} ✅".format(account, aws_region))
    except Exception as e:
        print("{} in {} region {} ❌".format(e,account,aws_region))

    try:
        delete_configuration_recorder = config_client.delete_configuration_recorder(ConfigurationRecorderName="default")
        print("Deleted Configuration Recorder in {} region {} ✅".format(account, aws_region))
    except Exception as e:
        print("{} in {} region {} ❌".format(e,account,aws_region))
    return ""





if __name__ == '__main__':

    # Setup command line arguments
    parser = argparse.ArgumentParser(
        description='Link AWS Accounts to central Config Account')
    #parser.add_argument('--master_account', type=str, required=True, help="AccountId for Central AWS Account")
    parser.add_argument(
        'input_file',
        type=argparse.FileType('r'),
        help='Path to CSV file containing the list of account IDs')
    parser.add_argument('--assume_role',
                        type=str,
                        required=True,
                        help="Role Name to assume in each account")
    parser.add_argument(
        '--enabled_regions',
        type=str,
        help=
        "comma separated list of regions to enable Config. If not specified, all available regions enabled"
    )
    args = parser.parse_args()

    # Validate master accountId
    #if not re.match(r'[0-9]{12}',args.master_account):
    #    raise ValueError("Master AccountId is not valid")

    # Generate dict with account & email information
    aws_account_dict = []

    for acct in args.input_file.readlines():
        split_line = acct.rstrip()
        if len(split_line) < 1:
            print("Unable to process line: {}".format(acct))
            continue

        if not re.match(r'[0-9]{12}', str(split_line)):
            print("Invalid account number {}, skipping".format(split_line))
            continue

        aws_account_dict.append(split_line)
    print("List of AWS accounts is {}".format(aws_account_dict))

    # Getting Config regions
    session = boto3.session.Session()
    config_regions = []
    if args.enabled_regions:
        config_regions = [
            str(item) for item in args.enabled_regions.split(',')
        ]
        print("Disabling Config in these regions: {}".format(config_regions))
    else:
        config_regions = session.get_available_regions('config')
        print("Disabling Config in all available regions {}".format(
            config_regions))

    failed_accounts = []
    for account in aws_account_dict:
        try:
            session = assume_role(account, args.assume_role)

            for aws_region in config_regions:

                config_client = session.client('config',
                                               region_name=aws_region)

                if aws_region == "ap-east-1":
                    try:
                        recorder_list = config_client.describe_configuration_recorders(
                        )

                        if len(recorder_list["ConfigurationRecorders"]) == 0:
                            print("No recorders exist in {} in {} 😞".format(
                                account, aws_region))
                        else:
                            print(disable_config(config_client,account,aws_region))

                    except Exception as e:
                        print("Account {} has {} region disabled ❌".format(
                            account, aws_region))

                else:

                    recorder_list = config_client.describe_configuration_recorders(
                    )

                    if len(recorder_list["ConfigurationRecorders"]) == 0:
                        print("No recorders exist in {} in {} 😞".format(
                            account, aws_region))
                    else:
                        if aws_region == "us-east-1":
                            print(
                                "Not disabling config in the {} in region {}".
                                format(account, aws_region))
                        else:
                            print(disable_config(config_client,account,aws_region))

        except Exception as e:
            print("{} ❌".format(e))
