import subprocess
import os


def git_tag():
    '''rather than hard code the script release, read it directly from the repository'''
    #  set the command which prints the git tags for the folder containing the script that is being executed. The tag looks like "v1.2.0-3-gccfd"
    cmd = "git -C " + os.path.dirname(os.path.realpath(__file__)) + " describe --tags"
    #  use subprocess to execute command
    proc = subprocess.Popen([cmd], stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
    out, err = proc.communicate()
    #  return standard out, removing any new line characters
    return out.rstrip().decode("utf-8")

if __name__ == "__main__":
    print(git_tag())