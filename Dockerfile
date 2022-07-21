FROM python:3.7
RUN apt-get update && apt-get upgrade -y && apt-get -y install rsync sshpass
RUN pip install dxpy==0.326.1
RUN mkdir -p /mokaguys/apps/code /mokaguys/logfiles /mokaguys/dx_downloads
# when building the docker image, the docker build command should be performed in the same folder as the code
# this command adds the contents of the local dir to the below location in the docker image
# it is put here so to that the relative file paths to things like the api tokens match those when running outside of docker.
ADD ./ /mokaguys/apps/code
WORKDIR /mokaguys
CMD ["python","/mokaguys/apps/code/archer_archive_script.py"]