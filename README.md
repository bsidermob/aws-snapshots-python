# Lambda AWS EC2 snapshot script

This Python script executes snapshot/AMI creation of running EC2 instances which have
termination protection on. Snapshots/AMIs are cleaned up after they turn 7 days old.

I'm running it in Lambda on an automated basis. Lambkin does the deployment and
sets cron schedule in CloudWatch.
