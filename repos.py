#!/usr/bin/env python
# coding: utf-8
import sys
from os import path, system, listdir
from collections import namedtuple

Repo = namedtuple('Repo', 'vcs slug description')


class Repo(object):
    def __init__(self, alias, vcs, features, service, slug, description):
        self.alias = alias
        self.vcs = vcs
        self.features = features
        self.service = service
        self.slug = slug
        self.description = description

    def url(self, section):
        if self.service == 'bitbucket':
            if self.vcs == 'hg':
                base_url = 'https://bitbucket.org/%s' % self.slug
            elif self.vcs == 'git':
                base_url = 'git@bitbucket.org:%s.git' % self.slug
        elif self.service == 'github':
            if self.vcs != 'git':
                raise NotImplementedError('Github only supports git')
            else:
                base_url = 'git@github.com:%s.git' % self.slug
        else:
            raise NotImplementedError('Currently %s is not suported as service' % self.service)

        if section == 'code':
            return base_url
        elif section == 'wiki':
            if self.service == 'bitbucket':
                return base_url + '/wiki'
            elif self.service == 'github':
                return base_url.replace('.git', '.wiki.git')
        else:
            raise NotImplementedError('Unknown section %s' % section)

    def web(self, section=None):
        if self.service == 'bitbucket':
            url = 'https://bitbucket.org/%s' % self.slug
        elif self.service == 'github':
            url = 'https://github.com/%s' % self.slug
        else:
            raise NotImplementedError('Currently %s is not suported as service' % self.service)

        if section == 'wiki':
            url += '/wiki'

        return url

    def path(self, section, repos_root):
        base_path = path.join(repos_root, self.alias)
        if section == 'code':
            return base_path
        elif section == 'wiki':
            return base_path + '-wiki'
        else:
            raise NotImplementedError('Unknown section %s' % section)

    def __str__(self):
        return self.alias

    def long_description(self):
        return '%s: %s (%s at %s, %s, %s)' % (self.alias, self.description,
                                              self.slug, self.service,
                                              self.vcs,
                                              '-'.join(self.features))


class ReposHandler(object):
    def __init__(self, repos, repos_root):
        self.repos = repos
        self.repos_root = repos_root

    def filter_repos(self, filters):
        if not filters:
            filtered = self.repos
        else:
            filters = [f.lower() for f in filters]

            filtered = [repo for repo in self.repos
                        if any(f in repo.long_description().lower()
                               for f in filters)]

        return filtered

    def filter_one_repo(self, filter_):
        repos = self.filter_repos([filter_,])
        if not repos:
            print('No repo matching the filter')
        elif len(repos) > 1:
            print('More than one repo matched the filter:')
            print('\n'.join(repo.long_description() for repo in repos))
        else:
            return repos[0]

    def vcs_action_on_repos(self, filters, vcs_action):
        repos = self.filter_repos(filters)

        for repo in repos:
            print('-' * 80)
            print(repo.long_description())
            if 'code' in repo.features:
                print(' -- Code --')
                vcs_action(repo, 'code')
            if 'wiki' in repo.features:
                print(' -- Wiki --')
                vcs_action(repo, 'wiki')

    def update(self, *filters):
        self.vcs_action_on_repos(filters, self.update_vcs)

    def clean(self, *filters):
        self.vcs_action_on_repos(filters, self.clean_vcs)

    def status(self, *filters):
        self.vcs_action_on_repos(filters, self.status_vcs)

    def update_vcs(self, repo, section):
        repo_url = repo.url(section)
        repo_path = repo.path(section, self.repos_root)

        if path.exists(repo_path):
            if repo.vcs == 'hg':
                pull_command = 'hg pull -u'
            elif repo.vcs == 'git':
                pull_command = 'git pull'

            command = '(cd %s && %s)' % (repo_path, pull_command)
        else:
            if repo.vcs == 'hg':
                clone_command = 'hg clone'
            elif repo.vcs == 'git':
                clone_command = 'git clone'

            command = '%s %s %s' % (clone_command, repo_url, repo_path)

        system(command)

    def clean_vcs(self, repo, section):
        repo_path = repo.path(section, self.repos_root)

        if repo.vcs == 'hg':
            clean_command = 'hg revert --all --no-backup'
        elif repo.vcs == 'git':
            clean_command = 'git checkout -- .'

        command = '(cd %s && %s)' % (repo_path, clean_command)
        system(command)

    def status_vcs(self, repo, section):
        repo_path = repo.path(section, self.repos_root)

        if repo.vcs == 'hg':
            clean_command = 'hg status'
        elif repo.vcs == 'git':
            clean_command = 'git status'

        command = '(cd %s && %s)' % (repo_path, clean_command)
        system(command)

    def code(self, editor, file_, filter_):
        return self.open_vcs_file('code', editor, filter_, file_, any_extension=False)

    def wiki(self, editor, file_, filter_):
        return self.open_vcs_file('wiki', editor, filter_, file_, any_extension=True)

    def wiki_web(self, browser, url, filter_):
        repo = self.filter_one_repo(filter_)
        if repo:
            full_url = '%s/%s' % (repo.web('wiki'), url)
            system('%s %s' % (browser, full_url))

    def run(self, command, *filters):
        repos = self.filter_repos(filters)
        for repo in repos:
            print('--', repo, '--')
            print()
            system('(cd %s && %s)' % (repo.path('code', self.repos_root),
                                      command))
            print()

    def open_vcs_file(self, section, editor, filter_, file_, any_extension=False):
        repo = self.filter_one_repo(filter_)
        if repo:
            file_path = path.join(repo.path(section, self.repos_root), file_)
            possible_files = []

            if any_extension:
                directory = path.dirname(file_path)

                if path.exists(directory):
                    possible_files = [path.join(directory, file_name)
                                      for file_name in listdir(directory)
                                      if file_name.split('.')[0] == file_]
            else:
                if path.exists(file_path):
                    possible_files = [file_path,]

            if not possible_files:
                print('File does not exists')
            elif len(possible_files) > 1:
                print('Many files on the wiki with that name:')
                print('\n'.join(possible_files))
            else:
                system('%s %s' % (editor, possible_files[0]))

    def list(self, *filters):
        repos = self.filter_repos(filters)
        for repo in repos:
            print(repo.long_description())

    def web(self, *filters):
        repos = self.filter_repos(filters)
        for repo in repos:
            print(repo.long_description())
            print(repo.web())

    @classmethod
    def find_repos_config(cls, start_path):
        current_path = start_path
        while current_path:
            config_path = path.join(current_path, 'repos.config')
            if path.exists(config_path):
                return config_path
            else:
                if current_path == '/':
                    current_path = None
                else:
                    current_path = path.dirname(current_path)

    @classmethod
    def read_repos_from_file(cls, file_path):
        repos = []
        with open(file_path) as repos_file:
            for line in repos_file.read().strip().split('\n'):
                data = line.split('|')
                alias, vcs, features, service, slug, description = data
                features = features.split(',')

                repo = Repo(alias=alias,
                            vcs=vcs,
                            features=features,
                            service=service,
                            slug=slug,
                            description=description)
                repos.append(repo)

            if len(repos) != len(set(repo.alias for repo in repos)):
                raise ValueError('There are repos with the same alias')
        return repos


if __name__ == '__main__':
    current_path = path.abspath('.')
    config_path = ReposHandler.find_repos_config(current_path)
    if not config_path:
        print('Unable to find repos.config')
        sys.exit(1)

    handler = ReposHandler(ReposHandler.read_repos_from_file(config_path), current_path)

    if len(sys.argv) < 2:
        print('Usage:')
        print('repos list FILTERS')
        print('repos status FILTERS')
        print('repos clean FILTERS')
        print('repos update FILTERS')
        print('repos code EDITOR FILE FILTERS')
        print('repos wiki EDITOR FILE FILTERS')
        print('repos wiki_web BROWSER URL FILTERS')
        print('repos run COMMAND FILTERS')
        exit()
    action = sys.argv[1]

    method = getattr(handler, action)
    if method:
        method(*sys.argv[2:])

