#!/bin/bash
set -x

# variables
tmp=$(mktemp)
function_name="ec2-volumes-backup"
# specify list of environment here, each env on new line
list_of_environments="default"

# Deploy to environments in loop
for environment in $list_of_environments
do
	echo "working on $environment"
	lowercase_environment=$(echo $environment | tr '[:upper:]' '[:lower:]')
	export AWS_PROFILE=$environment
	jq '.function = "'${lowercase_environment}-${function_name}'"' metadata.json > "$tmp" && mv "$tmp" metadata.json
	cp ${function_name}.py ${lowercase_environment}-${function_name}.py
	lambkin publish --role "lambda_basic_execution"
	rm ${lowercase_environment}-${function_name}.py
	lambkin schedule --cron '0 12 * * ? *'
done


# This below isn't actual but can be useful for debugging
# AWS function name is defined in metadata.json
# FUNCTION_NAME=$(cat metadata.json | jq '.function' --raw-output)

# Install virtual environment
#sudo apt-get install -y jq
#sudo pip install lambkin virtualenv

# Install dependcies and such
#lambkin build

# Publish the function
#lambkin publish --role "lambda_basic_execution"

# Test if the function works bu running it
# lambkin run

# Define function's run schedule
#lambkin schedule --rate '1 day'