"""
to check for archived folders on the archer server and upload to the DNANexus project
on the archer platform projects are archived after 45 days. 
All project files are in a folder named with an integer (e.g. 4767) in /var/www/analysis
Look through folders and identify those not on the already archived list
Then look in each project folder for a file named [projectno].tar.gz
If tar.gz file present project is archived on the Archer platform and can be backed up to DNAnexus
List the contents and locations of all files in the project folder (including the symlinks to the FASTQs) and save as a file
Capture the project name from other files in the folder (i.e. ADX21030)
Transfer the project folder to the genomics server with rsync
make tar.gz of the whole project folder
Find the matching project in DNANexus 
Upload it to DNA Nexus along with the locations file and delete from the genomics server
add archer project id (e.g. 4767) to the list of archived projects
#TODO consider possible edge case for archer project ids that are >4 or <4 characters. ?possible these would not be handled well by this section of th script

This script was developed by the Viapath Genome Informatics team
July 2022
"""

import os, datetime, subprocess
import git_tag
import archer_archive_config as config

class ArcherArchive():
	def __init__(self):
		self.now = str('{:%Y%m%d_%H%M%S}'.format(datetime.datetime.now()))
		# Set script log file path and name
		self.script_logfile_path = config.script_logfile_folder
		self.logfile_name = self.script_logfile_path + "/" + self.now + "archivelog.txt"
		# Open the script logfile for logging throughout script.
		self.script_logfile = open(self.logfile_name, 'a')
	
	def set_up_ssh_known_hosts(self):
		"""
		Need to add the archer server host into the known hosts otherwise any ssh command will return an interactive prompt that the authenticity of the host cannot be established
		Therefore we can run a command which tests if the server is in the known hosts list and if not it's added using ssh-keygen and ssh-keyscan
		This is run once each time the docker image is run.
		Returns True if host was added
		"""
		# make ~./ssh and ~/.ssh/known_hosts
		# if the host is not present in this file
		# use ssh-keyscan to get the key and add it in.
		# repeat the ssh-keygen command - this should now return a string which includes "# Host grpvgaa01.viapath.local found" - stdout can be tested for this
		# NB expect some outputs in stderr from the ssh-keyscan command at this stage
		cmd="mkdir -p ~/.ssh; touch ~./ssh/known_hosts;\
			if [ -z $(ssh-keygen -F grpvgaa01.viapath.local) ]; then \
				ssh-keyscan -H grpvgaa01.viapath.local >> ~/.ssh/known_hosts; fi; ssh-keygen -F grpvgaa01.viapath.local"
		out, err = self.execute_subprocess_command(cmd)

		if self.success_in_stdout(out, "Host grpvgaa01.viapath.local found"):
			self.logger("host added to known hosts ok", "SSH set up")
			return True
		else:
			self.logger("host NOT added to known hosts", "SSH set up") # Rapid7 alert set up
			return False

	def list_archer_projects(self):
		"""
		List all projects in /var/www/analysis on the Archer platform (when config.testing=True it looks in /var/www/analysis/test1 instead)
		Yields project ids (format 4 digits e.g.4690)
		"""
		# ssh on to archer platform using ssh pass and list the contents of /var/www/analysis (/var/www/analysis/test1 when testing)
		if config.testing:
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local ls %s" % (
					config.path_to_archerdx_pw, 
					config.path_to_analysis_test_folder) 
		else:
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local ls %s" % (
					config.path_to_archerdx_pw, 
					config.path_to_analysis_folder) 
		out,err = self.execute_subprocess_command(cmd)
		self.logger("command run to list projects: %s" % (cmd), "Archer archive")
		# for each item in the out (list of items in the /var/www/analysis folder) yeild the name if length=4 
		for folder_name in out.split("\n"):
			self.logger("checking folder %s" % (folder_name), "Archer archive")
			if len(folder_name) == 4:
				self.logger("identified project %s" % (folder_name), "Archer archive")
				yield folder_name
			else:
				self.logger("Archer project not identified.", "Archer archive")

	def check_previously_archived(self,archer_project_ID):
			"""
			Check if project is in the list of previously archived projects (config.path_to_archived_project_ids)
			input: Archer project id (####)
			output: True/False
			#TODO consider possible outcomes if eg prev archived run 123 on list, and run 1234 identified. Linked to possibility that archer project ID is not 4 characters (which would cause issues elsewhere)
			"""
			archived_runs = open(config.path_to_archived_project_ids)
			archived_runs_list = archived_runs.read().splitlines()
			# check if project is on list of previously archived projects. Return True if it is, False if not
			if archer_project_ID in archived_runs_list:
				self.logger("Archer project %s is on the list of archived projects. No further archiving required" % (archer_project_ID), "Archer archive")
				return True
			else:
				self.logger("Archer project %s has not previously been archived. Proceed to checking if it is archived on the Archer platform" % (archer_project_ID), "Archer archive")
				return False

	def check_project_archived(self,archer_project_ID):
		"""
		Takes archer project ID (####) as input
		looks in the project folder in the archer server and check for a .tar.gz file
		if that's present, the project has been archived in the Archer platform and the archive can be transferred to DNA Nexus
			-then looks back at the contents of the project folder to find the ADX project name (ADX###)
			#TODO future development: if .tar.gz file present but no files matching ADX# identified the script will error
			projects should have ADX in fastq file names etc because this is also used by the genomics_server_download archer_script.py
			-return the adx project name (ADX###)
		if not, logs that the project isn't ready for archiving
			-return None
		"""		
		if config.testing:
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local ls %s" % (
					config.path_to_archerdx_pw, 
					os.path.join(config.path_to_analysis_test_folder,archer_project_ID))
		else:
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local ls %s" % (
					config.path_to_archerdx_pw, 
					os.path.join(config.path_to_analysis_folder,archer_project_ID))
		out,err = self.execute_subprocess_command(cmd)
		# look through list of contents for file "archer_project_ID.tar.gz"
		archer_tar = archer_project_ID + ".tar.gz"
		if archer_tar in out.split("\n"):
			for file in out.split("\n"):
				if file.startswith("ADX"):
					project_adx = file.split("_",1)[0]
					self.logger("Project %s %s has been archived in Archer software. Can be backed up to DNA Nexus." % (archer_project_ID,project_adx), "Archer archive")
					return project_adx
		# if no .tar.gz file present file is not ready for archiving
		else:
			self.logger("Project %s not yet archived in Archer software. Move on to next project" % (archer_project_ID), "Archer archive")
			return None

	def list_archer_project_files(self,archer_project_ID):
		"""
		create txt file with ls -l of the archer project folder
		takes archer project ID (####) as input
		Returns the path of the fastq locations file that is created as an item in a list. 
		"""
		# echo $? returns exit status of last command, non zero means it's failed
		fastq_loc_file = "%s_fastq_loc.txt" % (os.path.join(config.fastq_locations_folder,archer_project_ID))
		if config.testing: #point to analysis_test_folder
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local ls -l %s > %s; echo $?" % (
					config.path_to_archerdx_pw, 
					os.path.join(config.path_to_analysis_test_folder,archer_project_ID),
					fastq_loc_file)
		else:
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local ls -l %s > %s; echo $?" % (
					config.path_to_archerdx_pw,
					os.path.join(config.path_to_analysis_folder,archer_project_ID),
					fastq_loc_file)
		out,err = self.execute_subprocess_command(cmd)
		# check for errors in the stdout
		if self.success_in_stdout(out.rstrip(), "0"):
			self.logger("Fastq locations file for project %s generated." % (archer_project_ID), "Archer archive")
			return [fastq_loc_file] #return the file as a list for downstream processing
		else:
			# Rapid 7 alert set up
			self.logger("ERROR: Failed to generate fastq locations file for project %s." % (archer_project_ID), "Archer archive")
			return None

	def copy_archer_project(self,archer_project_ID):
		"""
		Copy the archer project folder to the genomics server using rsync
		Only do this if the tar.gz file is present in /var/www/analysis/archer_project_ID (check_project_archived=True) AND no processed runs log for this archer_project_ID (check_if_already_completed=False)
		folder will be rsync copied to config.copy_location 
		Input: archer_project_ID
		Output: If rsync successful returns True
		"""
		# rsync archer project folder to genomics server. -r recursive, ensures all subfiles and folders copied, -t preserves modification times
		# echo $? returns exit status of last command, non zero means it's failed
		if config.testing:
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw rsync -rt s_archerupload@grpvgaa01.viapath.local:%s %s;\
				echo $?" % (
					config.path_to_archerdx_pw, 
					os.path.join(config.path_to_analysis_test_folder,archer_project_ID),
					config.copy_location
					)
		else:
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw rsync -rt s_archerupload@grpvgaa01.viapath.local:%s %s;\
				echo $?" % (
					config.path_to_archerdx_pw, 
					os.path.join(config.path_to_analysis_folder,archer_project_ID),
					config.copy_location
					)
		# capture stdout and look for exit code
		out,err = self.execute_subprocess_command(cmd)
		self.logger("rsync cmd: %s\nout: %s" % (cmd,out), "Archer archive")
		if self.success_in_stdout(out.rstrip(), "0"):
			self.logger("folder for Archer project %s copied to genomics server." % (archer_project_ID), "Archer archive")
			return True
		else:
			# Rapid 7 alert set up
			self.logger("ERROR: Failed to copy Archer project folder" % (archer_project_ID), "Archer archive")	
			return False		

	def create_project_tar(self,archer_project_ID):
		"""
		create tar archive of the copied project folder
		Returns tarfile name 
		"""
		# cd to the project folder location
		# c creates an archive
		# f specify the filename of the archive
		# z filters the archive through gzip
		# provide the folder name, not the full filepath to ensure the tar doesn't contain the full path from root
		# redirect stderr to stdout so we can test for errors
		tarfile_name = "%s.tar.gz" % (archer_project_ID)
		cmd = "cd %s; tar -czf %s %s 2>&1" % (config.copy_location,tarfile_name,archer_project_ID)
		out, err = self.execute_subprocess_command(cmd)
		self.logger("tar cmd: %s\nout: %s" % (cmd,out), "Archer archive")
		# assess stdout+stderr - if successful tar does not return any output
		if len(out) ==0:
			self.logger("Tar of archer project %s generated successfully" % (archer_project_ID),"Archer archive")
			return tarfile_name
		else:
			# Rapid 7 alert set up 
			self.logger("ERROR: failed to generate tar of archer project %s. n\Error message: %s. \nProject will not be archived." % (archer_project_ID,out),"Archer archive")
			return None

	def find_DNAnexus_project(self,archer_project_ID,project_adx):
		"""
		search for matching DNAnexus project using project_adx (archer run name: ADX###)
		returns the DNAnexu projectID and projectname
		If no matching projects, or greater than 1 project matches will return error- send to rapid 7
		"""
		# search DNAnexus for project matching project_adx (ADX###)
		#cmd = config.source_command+";dx find projects --name='*%s*' --auth-token %s" % (project_adx,config.Nexus_API_Key)
		cmd = "dx find projects --name='*%s*' --auth-token %s" % (project_adx,config.Nexus_API_Key)
		out,err = self.execute_subprocess_command(cmd)
		self.logger("find_DNAnexus_project() cmd: %s" % (cmd),"Archer archive")
		# count number of projects returned. If unable to identify a single matching project return error
		# note: if one project found len(matchingprojects)=2 because there is a newline 
		matching_projects = out.split("\n")
		if len(matching_projects) != 2:
			# Rapid 7 alert set up 
			self.logger("ERROR: Unable to identify a single DNAnexus project matching %s. Unable to backup Archer project %s" % (project_adx,archer_project_ID), "Archer list projects")
			return None,None
		else:
			# extract the projectid and projectname for use later
			projectid,colon,projectname,access = matching_projects[0].split(" ")
			self.logger("DNAnexus project identified matching %s (Archer project %s). Project name: %s." % (project_adx,archer_project_ID,projectname),"Archer list projects")
			return projectid,projectname

	def upload_to_dnanexus(self,file_list,dnanexus_projectname):
		"""
		can be called twice- to upload tar.gz and fastq_loc file
		takes a file and the DNAnexus project as input
		returns True if upload successfil
		"""
		# read list of files to upload into a string to include in the upload command
		list_of_files = " ".join(file_list)
		# generate command to upload file to DNAnexus project
		cmd = "%s --auth-token %s --project %s --do-not-compress %s" % (
			config.path_to_dx_upload_agent,
			config.Nexus_API_Key,
			dnanexus_projectname,
			list_of_files) 
		out,err = self.execute_subprocess_command(cmd)
		self.logger("dnanexus upload agent command: %s\nout: %s\n%s" % (cmd,out,err),"Archer archive")
		# check output of this command
		if out.startswith("file-"):
		#if self.success_in_stdout(out,"file*"):
			self.logger("files %s successfully uploaded to DNAnexus project %s" % (list_of_files,dnanexus_projectname),"Archer archive")
			return True
		else:
			# Rapid 7 alert set up
			self.logger("ERROR: failed to upload file %s to DNAnexus project %s" % (list_of_files,dnanexus_projectname),"Archer archive")
			return False

	def cleanup_archer_project_folder(self,archer_project_ID):
		"""
		empty project folder (but leave folder there, i.e. do not delete the folder)
		Once project is archived in DNAnexus the copy on the archer platform can be deleted.
		Returns true if successful
		"""
		# ssh on to archer platform using ssh pass and empty the project folder.
		if config.testing:
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local rm -r %s/*; echo $?" % (
					config.path_to_archerdx_pw, 
					os.path.join(config.path_to_analysis_test_folder,archer_project_ID))
		else:
			cmd = "archer_pw=$(<%s); \
				sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local rm -r %s/*; echo $?" % (
					config.path_to_archerdx_pw, 
					os.path.join(config.path_to_analysis_folder,archer_project_ID)) 
		self.logger("command to cleanup project on archer server: %s" %(cmd), "Archer archive")
		out,err = self.execute_subprocess_command(cmd)
		self.logger("clean up archer project cmd: %s\nout: %s" % (cmd,out),"Archer archive")
		# check for success in stdout
		if self.success_in_stdout(out,"0"):
			self.logger("Archer project folder %s emptied." % (archer_project_ID),"Archer archive")
			return True
		else:
			# Rapid 7 alert set up
			self.logger("ERROR: failed to correctly empty archer project folder %s." % (archer_project_ID),"Archer archive")
			return False

	def cleanup_archer_fastqs(self,project_adx):
		"""
		Need to delete the fastqs from the watched folder on the Archer platform
		uses the archer project name ADX# to identify the fastq filesx
		Call list_archer_fastq_for_deletion() to add the files to the log and get the path used for deleting the files
		Returns True if successful
		"""
		# call list_archer_fastq_for_deletion() to get path
		path_to_fastqs = self.list_archer_fastq_for_deletion(project_adx)
		# ssh on to archer platform using ssh pass and empty the project folder
		cmd = "archer_pw=$(<%s); \
			sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local rm %s; echo $?" % ( 
			config.path_to_archerdx_pw, 
			path_to_fastqs) 
	
		self.logger("command to cleanup fastq files: %s" % (cmd), "Archer archive")
		out,err = self.execute_subprocess_command(cmd)
		# check for success in stdout
		if self.success_in_stdout(out,"0"):
			self.logger("FASTQs for archer project %s deleted from picked_up_files folder." % (project_adx),"Archer archive")
			return True
		else:
			# Rapid 7 alert set up
			self.logger("ERROR: failed to correctly delete the FASTQ files for project %s" % (project_adx),"Archer archive")
			return False

	def list_archer_fastq_for_deletion(self,project_adx):
		"""
		list the fastqs that will be deleted and write them to the logfile
		input: project_adx (ADX###)
		output: the path to the fastqs (so the path used to list the fastqs is the same as the path to delete them)
		"""
		# first get the path to the fastq files location
		if config.testing:
			path_to_fastqs = "%s*.fastq.gz" % (os.path.join(config.path_to_picked_up_test_files,project_adx))
		else:
			path_to_fastqs = "%s*.fastq.gz" % (os.path.join(config.path_to_picked_up_files,project_adx))
		# command to list fastq files to be deleted
		cmd = "archer_pw=$(<%s); \
			sshpass -p $archer_pw ssh s_archerupload@grpvgaa01.viapath.local ls %s; echo $?" % ( 
			config.path_to_archerdx_pw, 
			path_to_fastqs) 

		out,err = self.execute_subprocess_command(cmd)
		# write the list of files to the log
		self.logger("List of fastq files to be deleted from %s for project %s:\n%s" % (path_to_fastqs,project_adx,out),"Archer archive")
		# return the file path to be used by clean_up_archer_fastqs()
		return path_to_fastqs

	def update_list_archived_projects(self,archer_project_ID,project_adx):
		"""
		Add project id (e.g.4798) to the list of archived runs. 
		This will prevent future archiving of the run- the file is searched by check_previously_archived() 
		Inputs:		archer project ID (4 digits)
		Outputs:	updated archived projects list (config.path_to_archived_project_ids)
		"""
		# open the archived projects file and add the project ID of the archived project to the list
		with open(config.path_to_archived_project_ids,"a") as archived_projects_list:
			archived_projects_list.write("%s\n" % (archer_project_ID))
			self.logger("Project ID %s added to archived projects list" % (project_adx),"Archer archive")

	def cleanup_genomics_server(self,archer_project_ID):
		"""
		If the files have been transferred to the server ok we can delete the project folder and tar.
		Do not delete the fastq_locations file, to return the full record of 
		Inputs:		archer_project_ID (four digit ID)
		Outputs:	Returns True if all files deleted successfully
		"""
		# downloaded fastq files location on genomics server
		path_to_project_folder = os.path.join(config.copy_location,"%s" % (archer_project_ID))
		# command to delete the downloaded fastq files
		cmd = "rm -r %s*; echo $?" % (path_to_project_folder)
		out, err = self.execute_subprocess_command(cmd)
		if self.success_in_stdout(out, "0"):
			self.logger("Successfully deleted project folder and tar.gz file for project %s from genomics server" % (archer_project_ID), "Archer Archive")
			return True
		else:
			# Rapid7 alert set up
			self.logger("WARNING: Archer archiving files not deleted from genomics server: project folder %s and tarfile %s.tar.gz" % (archer_project_ID,archer_project_ID), "Archer Archive")
			return False

	def success_in_stdout(self,stdout, expected_txt=False):
		"""
		Returns True if expected statement in stdout
		"""
		if expected_txt:
			if expected_txt in stdout:
				return True

	def execute_subprocess_command(self, command):
		"""
		Input = command (string)
		Takes a command, executes using subprocess.Popen
		Returns =  (stdout,stderr) (tuple)
		universal_newlines=True is required to force the outputs to be strings not bytes in python 3. For python 3.7 onwards can use text=True instead
		"""
		proc = subprocess.Popen(
			[command],
			stderr=subprocess.PIPE,
			stdout=subprocess.PIPE,
			shell=True,
			universal_newlines=True, 
			executable="/bin/bash",
		)
		# capture the streams
		return proc.communicate()

	def logger(self, message, tool):
		"""
		Write log messages to the system log.
		Arguments:
		message (str)
			Details about the logged event.
		tool (str)
			Tool name. Used to search within the insight ops website.
		"""
		# Create subprocess command string, passing message and tool name to the command
		log = "/usr/bin/logger -t %s '%s'" % (tool, message)

		if subprocess.call([log], shell=True) == 0:
			# If the log command produced no errors, record the log command string to the script logfile.
			self.script_logfile.write(tool + ": " + message + "\n")
		# Else record failure to write to system log to the script log file
		else:
			self.script_logfile.write("Failed to write log to /usr/bin/logger\n" + log + "\n")

	def go(self):
		"""
		Calls all other functions
		"""
		# set up ssh hosts
		if self.set_up_ssh_known_hosts():
			# list projects on archer platform by archer project id (####)
			for project in self.list_archer_projects():
				# check if the project is on the previously archived list
				if not self.check_previously_archived(project):
					# check if project archived on archer, return project name (ADX##) if so
					adx_project_name = self.check_project_archived(project)
					if adx_project_name:
						# generate file listing locations of files in the archer project folder. Filename is returned as a list
						files_to_upload = self.list_archer_project_files(project) #returns a list
						if files_to_upload:
							# rsync archer project folder to genomics server
							if self.copy_archer_project(project):
								# tar the archer project folder
								tar_name = self.create_project_tar(project)
								if tar_name:
									# add tar name (with path) to a list of files to be uploaded to DNAnexus
									tar_path = os.path.join(config.copy_location,tar_name)
									files_to_upload.append(tar_path)
									# look for the DNAnexus project
									projectID,projectname = self.find_DNAnexus_project(project,adx_project_name)
									# if no unique project found projectid and projectname will be None
									if projectID:
										# upload tar.gz and fastq locations file to DNAnexus
										if self.upload_to_dnanexus(files_to_upload,projectname):
											#clean up archer platform
											if self.cleanup_archer_project_folder(project) and self.cleanup_archer_fastqs(adx_project_name):
												#add archer project ID to archived project list
												self.update_list_archived_projects(project,adx_project_name)
												self.cleanup_genomics_server(project)

if __name__ == "__main__":
	archer = ArcherArchive()
	archer.go()	
