# Lambda AWS EC2 volumes snapshot script

This executes snapshot creation of running EC2 instances which have
termination protection on. Snapshots are cleaned up after they turn 7 days old.

I'm running it in Lambda on an automated basis.
