import os
testing = True
docker = True
# =====location of input/output files=====
# root of folder that contains the apps, automate_demultiplexing_logfiles and
# development_area scripts
# (2 levels up from this file)
document_root = "/".join(os.path.dirname(os.path.realpath(__file__)).split("/")[:-2])
resources_root=os.path.dirname(os.path.realpath(__file__))
logfile_folder = os.path.join(document_root,"logfiles")
script_logfile_folder = os.path.join(logfile_folder,"script_logfiles")
processed_runs_folder = os.path.join(logfile_folder,"processed_runs")
archive_logs_folder = os.path.join(logfile_folder,"archer_archive_logs")
fastq_locations_folder = os.path.join(archive_logs_folder,"fastq_locations")

# DNA Nexus authentication token
nexus_api_key_file = os.path.join(document_root,".dnanexus_auth_token")
with open(nexus_api_key_file, "r") as nexus_api:
	Nexus_API_Key = nexus_api.readline().rstrip()

# archerdx VM login
path_to_archerdx_pw = "{document_root}/.archerVM_pw".format(document_root=document_root)

copy_location = os.path.join(document_root,"dx_downloads")
path_to_watch_folder = "/watched/aledjones\@nhs.net/FusionPlexPanSolidTumorv1_0" #folder made by RLH 20210622
path_to_analysis_folder = "/var/www/analysis"
path_to_analysis_test_folder = "/var/www/analysis/test1"
path_to_picked_up_files = "/watched/aledjones\@nhs.net/FusionPlexPanSolidTumorv1_0/picked_up_files"
path_to_picked_up_test_files = os.path.join(path_to_analysis_test_folder,"fastqs")
export_environment = "export DX_API_TOKEN=%s" % Nexus_API_Key
path_to_archived_project_ids = os.path.join(document_root,archive_logs_folder,"archer_archived_projects.txt")

# when testing the script it may be easier to do so without running the docker image. Different paths are required for some inputs in this case
if docker:
    source_command = " source %s" % (os.path.join(resources_root,"resources","dx-toolkit","environment"))
    path_to_dx_upload_agent = os.path.join(resources_root,"resources","dnanexus-upload-agent-1.5.33-linux","ua")
else:
    source_command = " source %s" % (os.path.join(document_root,"apps","dx-toolkit","environment"))
    path_to_dx_upload_agent = os.path.join(document_root,"apps","dnanexus-upload-agent-1.5.33-linux","ua")