#!/usr/bin/env python3
# coding: utf-8
import sys
from os import system, putenv
from collections import namedtuple
from enum import Enum
from pathlib import Path

import requests
from termcolor import colored


class BadRepoConfig(Exception):
    """
    An error describing the config problem of a repo.
    """


class Service(Enum):
    """
    Supported services where repos can be hosted.
    """
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class VCS(Enum):
    """
    Supported version control systems.
    """
    GIT = "git"
    HG = "hg"


class VCSAction(Enum):
    """
    An action that can be executed in a cloned vcs repo.
    """
    UPDATE = "update"
    CLEAN = "clean"
    STATUS = "status"


class Section(Enum):
    """
    A section of the repo.
    """
    CODE = "code"
    WIKI = "wiki"


class Color(Enum):
    """
    Colors that we can use in the terminal output.
    """
    SUCCESS = "green"
    ERROR = "red"



class Repo:
    """
    A repository of code, with a name, and possibly a wiki too, and maybe a server where the code
    is live and running.
    """
    @classmethod
    def parse_line(cls, config_line, repos_root):
        """
        Parse a repos config line and build a Repo instance with that data.
        """
        data = config_line.split('|')
        alias = data[0]

        if len(data) != 7:
            msg = f"Repo {alias} doesn't honor the format: alias|vcs|sections|service|slug|server|descroption"
            raise BadRepoConfig(msg)

        alias, vcs, sections, service, slug, server, description = data

        try:
            vcs = VCS(vcs)
        except ValueError as err:
            msg = f"Unsupported vcs in repo {alias}: {vcs}"
            raise BadRepoConfig(msg) from err

        try:
            service = Service(service)
        except ValueError as err:
            msg = f"Unsupported repo hosting service in repo {alias}: {service}"
            raise BadRepoConfig(msg) from err

        if service in (Service.GITHUB, Service.GITLAB) and vcs != VCS.GIT:
            msg = f"Repo {alias} tries to use {service} with a VCS that isn't git"
            raise BadRepoConfig(msg)

        try:
            sections = [Section(section) for section in sections.split(",")]
        except ValueError as err:
            msg = f"Repo {alias} has invalid sections specified (comma separated list of: code,wiki)"
            raise BadRepoConfig(msg) from err

        return Repo(
            alias=alias,
            vcs=vcs,
            sections=sections,
            service=service,
            slug=slug,
            server=server,
            description=description,
            repos_root=repos_root,
        )

    def __init__(self, alias, vcs, sections, service, slug, server, description, repos_root):
        self.alias = alias
        self.vcs = vcs
        self.sections = sections
        self.service = service
        self.slug = slug
        self.server = server
        self.description = description
        self.repos_root = repos_root

    def clone_url(self, section):
        """
        Build the url used to clone this repo with a vcs.
        """
        if self.service == Service.BITBUCKET:
            if self.vcs == VCS.HG:
                base_url = f"https://bitbucket.org/{self.slug}"
            elif self.vcs == VCS.GIT:
                base_url = f"git@bitbucket.org:{self.slug}.git"
        elif self.service == Service.GITHUB:
            # vcs will be git
            base_url = f"git@github.com:{self.slug}.git"
        elif self.service == Service.GITLAB:
            # vcs will be git
            base_url = f"git@gitlab.com:{self.slug}.git"

        if section == Section.CODE:
            return base_url
        elif section == Section.WIKI:
            if self.service == Service.BITBUCKET:
                return f"{base_url}/wiki"
            elif self.service in (Service.GITHUB, Service.GITLAB):
                return base_url.replace(".git", ".wiki.git")

    def web_url(self, section=None):
        """
        Build the url used to visit this repo with a web browser.
        """
        if self.service == Service.BITBUCKET:
            url = f"https://bitbucket.org/{self.slug}"
        elif self.service == Service.GITHUB:
            url = f"https://github.com/{self.slug}"
        elif self.service == Service.GITLAB:
            url = f"https://gitlab.com/{self.slug}"

        if section == Section.WIKI:
            url += "/wiki"

        return url

    def path(self, section):
        """
        Path in which the repo will be cloned locally.
        """
        if section == Section.CODE:
            return self.repos_root / self.alias
        elif section == Section.WIKI:
            return self.repos_root / f"{self.alias}-wiki"

    def __str__(self):
        return self.alias

    def long_description(self):
        """
        Repo details described in a human readable string.
        """
        return f"{self.alias}: {self.description} ({self.slug} at {self.service.value})"

    def vcs_update(self, section):
        """
        Update the cloned repo, or clone it if not present.
        """
        repo_url = self.clone_url(section)
        repo_path = self.path(section)

        if repo_path.exists():
            if self.vcs == VCS.HG:
                pull_command = "hg pull -u"
            elif self.vcs == VCS.GIT:
                pull_command = "git pull"

            command = f"(cd {repo_path} && {pull_command})"
        else:
            if self.vcs == VCS.HG:
                clone_command = "hg clone"
            elif self.vcs == VCS.GIT:
                clone_command = "git clone"

            command = f"{clone_command} {repo_url} {repo_path}"

        result = system(command)
        return result == 0

    def vcs_clean(self, repo, section):
        """
        Clean changes done to the repo.
        """
        repo_path = repo.path(section)

        if self.vcs == VCS.HG:
            clean_command = "hg revert --all --no-backup"
        elif self.vcs == VCS.GIT:
            clean_command = "git checkout -- ."

        command = f"(cd {repo_path} && {clean_command})"
        result = system(command)
        return result == 0

    def vcs_status(self, repo, section):
        """
        Show the status of the repo.
        """
        repo_path = repo.path(section)

        if self.vcs == VCS.HG:
            status_command = "hg status"
        elif self.vcs == VCS.GIT:
            status_command = "git status"

        command = f"(cd {repo_path} && {status_command})"
        result = system(command)
        return result == 0

    def open_vcs_file(self, section, editor, file_, any_extension=False):
        """
        Find and open a specified file from the repo.
        """
        file_path = self.path(section) / file_
        possible_files = []

        if any_extension:
            parent_dir = file_path.parent

            if parent_dir.exists():
                possible_files = list(parent_dir.glob(f"{file_.name}.*"))
        else:
            if file_path.exists():
                possible_files = [file_path]

        if len(possible_files) == 1:
            system(f"{editor} {possible_files[0]}")
            return True, possible_files
        else:
            return False, possible_files

    def navigate_wiki(self, browser, url):
        """
        Open a browser to a specific page of the wiki.
        """
        full_url = f"{self.web_url(Section.WIKI)}/{url}"
        system(f"{browser} {full_url}")

    def navigate_server(self, browser):
        """
        Open a browser to the web server running the code.
        """
        system(f"{browser} {self.server}")

    def revive_server(self):
        """
        Do a background request to the server running the code, so it wakes up if it was put to
        sleep.
        """
        response = requests.get(self.server)
        response.raise_for_status()

    def run(self, command):
        """
        Run a command inside the repo.
        """
        repo_path = self.path(Section.CODE)
        putenv("REPO_PATH", repo_path)
        result = system(f"(cd {repo_path} && {command})")
        return result


class ReposHandler(object):
    """
    The app itself, exposing a set of actions that you can run over a set of repos.
    """
    def __init__(self, repos):
        self.repos = repos

    def filter_repos(self, filters):
        """
        Obtain the list of repos that match a given filter.
        IF no filter is specified, then all repos are returned.
        """
        if not filters:
            filtered = self.repos
        else:
            filters = [f.lower() for f in filters]

            filtered = [repo for repo in self.repos
                        if any(f in repo.long_description().lower()
                               for f in filters)]

            if filtered:
                print(colored(f"{len(filtered)} repos found", Color.SUCCESS.value))
            else:
                print(colored("No repos matching the filters", Color.ERROR.value))

        return filtered

    def iterate_filtered_repos(self, filters):
        """
        Iterate over the results of filter_repos, printing the title of the repo on each step.
        """
        repos = self.filter_repos(filters)
        for repo in repos:
            print(colored(f"-- {repo} --", Color.SUCCESS.value))
            yield repo

    def vcs_action_in_repos(self, filters, vcs_action):
        """
        Run a vcs action in a set of filtered repos.
        """
        repos_ok = []
        repos_err = []

        method_name = f"vcs_{vcs_action.value}"

        for repo in self.iterate_filtered_repos(filters):
            code_ok = True
            wiki_ok = True

            if Section.CODE in repo.sections:
                print(colored(" -- Code --", Color.SUCCESS.value))
                code_ok = getattr(repo, method_name)(Section.CODE)

                if not code_ok:
                    print(colored("Error running command", Color.ERROR.value))

            if Section.WIKI in repo.sections:
                print(colored(" -- Wiki --", Color.SUCCESS.value))
                wiki_ok = getattr(repo, method_name)(Section.WIKI)

                if not wiki_ok:
                    print(colored("Error running command", Color.ERROR.value))

            if code_ok and wiki_ok:
                repos_ok.append(repo)
            else:
                repos_err.append(repo)

            print()

        self.summary_errors(repos_ok, repos_err)

    def update(self, *filters):
        """
        Do a vcs update over a set of filtered repos.
        """
        self.vcs_action_in_repos(filters, VCSAction.UPDATE)

    def clean(self, *filters):
        """
        Do a vcs clean over a set of filtered repos.
        """
        self.vcs_action_in_repos(filters, VCSAction.CLEAN)

    def status(self, *filters):
        """
        Do a vcs status over a set of filtered repos.
        """
        self.vcs_action_in_repos(filters, VCSAction.STATUS)

    def code(self, editor, file_, *filters):
        """
        Open a vcs code file over a set of filtered repos.
        """
        return self.open_vcs_file(Section.CODE, editor, filters, file_, any_extension=False)

    def wiki(self, editor, file_, *filters):
        """
        Open a vcs wiki file over a set of filtered repos.
        """
        return self.open_vcs_file(Section.WIKI, editor, filters, file_, any_extension=True)

    def wiki_web(self, browser, url, *filters):
        """
        Navigate to a specific page of the wiki of a set of filtered repos.
        """
        for repo in self.iterate_filtered_repos(filters):
            repo.navigate_wiki(browser, url)

    def server(self, browser, *filters):
        """
        Navigate to the server running the code of a set of filtered repos.
        """
        for repo in self.iterate_filtered_repos(filters):
            repo.navigate_server(browser)

    def revive_server(self, *filters):
        """
        Do a request to the server running the code of a set of filtered repos, to wake it up if
        it's sleeping.
        """
        repos_ok = []
        repos_err = []

        for repo in self.iterate_filtered_repos(filters):
            print('Accessing server...')
            try:
                repo.revive_server()
                repos_ok.append(repo)
                print(colored("Done!", Color.SUCCESS.value))
            except:
                repos_err.append(repo)
                print(colored("Error:", Color.ERROR.value))

            print()

        self.summary_errors(repos_ok, repos_err)

    def run(self, command, *filters):
        """
        Run a command inside the folders of a set of filtered repos.
        """
        repos_ok = []
        repos_err = []
        for repo in self.iterate_filtered_repos(filters):
            result = repo.run(command)
            if result == 0:
                repos_ok.append(repo)
                print(colored("Done!", Color.SUCCESS.value))
            else:
                repos_err.append(repo)
                print(colored("Error running command", Color.ERROR.value))
            print()

        self.summary_errors(repos_ok, repos_err)

    def open_vcs_file(self, section, editor, filters, file_, any_extension=False):
        """
        Open files of a set of filtered repos.
        """
        repos_ok = []
        repos_err = []

        for repo in self.iterate_filtered_repos(filters):
            was_able_to_open, possible_files = repo.open_vcs_file(section, editor, file_,
                                                                  any_extension=any_extension)
            if was_able_to_open:
                repos_ok.append(repo)
            else:
                repos_err.append(repo)

                if possible_files:
                    print(colored("Many files on the wiki with that name:", Color.ERROR.value))
                    print('\n'.join(map(str, possible_files)))
                else:
                    print(colored("File does not exists", Color.ERROR.value))
            print()

        self.summary_errors(repos_ok, repos_err)

    def list(self, *filters):
        """
        Just list filtered repos info.
        """
        repos = self.filter_repos(filters)
        for repo in repos:
            print(repo.long_description())

    def show_urls(self, *filters):
        """
        Just list the urls of filtered repos.
        """
        for repo in self.iterate_filtered_repos(filters):
            print(repo.long_description())
            print(repo.web_url())
            print(repo.web_url('wiki'))
            print(repo.server)

    @classmethod
    def find_repos_config(cls, start_path):
        """
        Find the closest repos config file, navigating from the current dir backwards.
        """
        current_path = start_path
        while current_path:
            config_path = current_path / "repos.config"
            if config_path.exists():
                return config_path
            else:
                parent = current_path.parent
                if current_path == parent:
                    current_path = None
                else:
                    current_path = parent

    @classmethod
    def parse_file(cls, file_path, repos_root):
        """
        Parse a repos config file, and return the ReposHandler instance.
        """
        repos = []
        with open(file_path) as repos_file:
            for line in repos_file.read().strip().split('\n'):
                if not line.startswith('#') and line.strip():
                    repos.append(Repo.parse_line(line, repos_root))

            if len(repos) != len(set(repo.alias for repo in repos)):
                raise ValueError('There are repos with the same alias')

        return ReposHandler(repos)

    @classmethod
    def summary_errors(cls, repos_ok, repos_err):
        """
        Show a summary of ok and errors from actions in a set of repos.
        """
        if len(repos_ok) + len(repos_err) > 1:
            if repos_ok:
                print(colored('Success:', 'green'), ', '.join(map(str, repos_ok)))
            if repos_err:
                print(colored('Errors:', 'red'), ', '.join(map(str, repos_err)))

    @classmethod
    def show_help(cls):
        """
        Show the help message.
        """
        print(colored('Usage:', Color.SUCCESS.value))
        print('repos list FILTERS')
        print('repos status FILTERS')
        print('repos clean FILTERS')
        print('repos update FILTERS')
        print('repos code EDITOR FILE FILTERS')
        print('repos wiki EDITOR FILE FILTERS')
        print('repos wiki_web BROWSER URL FILTERS')
        print('repos server BROWSER FILTERS')
        print('repos revive_server BROWSER FILTERS')
        print('repos run "COMMAND" FILTERS')
        print('repos show_urls FILTERS')


def main():
    """
    When running from the command line, this is executed.
    """
    current_path = Path('.')
    config_path = ReposHandler.find_repos_config(current_path)
    if not config_path:
        print(colored('Unable to find repos.config', Color.ERROR.value))
        exit(1)

    handler = ReposHandler.parse_file(config_path, current_path)

    if len(sys.argv) < 2:
        handler.show_help()
        exit()

    action = sys.argv[1]
    method = getattr(handler, action, None)
    if method is None:
        print(colored(f'Unknown action: {action}', Color.ERROR.value))
        handler.show_help()
        exit()

    if method:
        try:
            method(*sys.argv[2:])
        except KeyboardInterrupt:
            print("Cancelled")


if __name__ == '__main__':
    main()
