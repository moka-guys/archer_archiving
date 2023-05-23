# archer_archiving v1.1.0
This script is for backing up data from the Archer analysis platform to DNAnexus for long term storage. The Archer analysis software runs on a virtual server with limited storage space (1TB), and new analyses fail if space runs out.

Once projects have been archived within the Archer analysis platform (set to be performed automatically after a certain time period), the project folder contents on the archer platform are copied to the Genomics Server with rsync, compressed with tar and uploaded to the relevant DNAnexus project. The project folder and associated fastq files are then deleted from the Archer server, leaving the (empty) project folder in place.

## Requirements
* Python 3
* DNA Nexus upload agent (v1.5.33-linux)
* rsync
* DNA Nexus sdk
* DNA Nexus API token
* Archer server password

## Docker
The scripts can be run from within a docker container when docker = True in the archer_archive_config.py file. This can be run using the command 
`sudo docker run --rm --log-driver syslog -v /var/log:/var/log -v /usr/local/src/mokaguys/logfiles:/mokaguys/logfiles -v /usr/local/src/mokaguys/dx_downloads:/mokaguys/dx_downloads -v /usr/local/src/mokaguys/.dnanexus_auth_token:/mokaguys/.dnanexus_auth_token -v /usr/local/src/mokaguys/.archerVM_pw:/mokaguys/.archerVM_pw archer_archiving:latest`
(replacing the tag `latest` as required).

### using ssh within the Docker image
It is necessary to add the archer server host to the known hosts, otherwise any ssh command will return an interactive prompt that the authenticity of the host cannot be established. As this must be done each time the docker image is run, a method is included in archer_archive_script.py, `set_up_ssh_known_hosts()`, using ssh-keygen and ssh-keyscan, that is run each time the script runs 

## Running the script
The Docker image is run daily as a CRON job (the python script doesn't work in cron due to an issue with the pythonpath run by CRON). 

### Testing mode
In the config file there is a testing variable.
When set to `True` an alternative folder location is used on the archer server, to avoid processing real runs during testing.

## Logging
Script logfiles are written to mokaguys/logfiles/script_logfiles/YYYYMMDD_TTTTTTarchivelog.txt

## Alerts
Alerts are sent to Slack when errors or warnings are sent to the system log.