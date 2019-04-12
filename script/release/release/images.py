from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import base64
import json
import os

import docker

from .const import REPO_ROOT
from .utils import ScriptError


class ImageManager(object):
    def __init__(self, version, latest=False):
        self.docker_client = docker.APIClient(**docker.utils.kwargs_from_env())
        self.version = version
        self.latest = latest
        if 'HUB_CREDENTIALS' in os.environ:
            print('HUB_CREDENTIALS found in environment, issuing login')
            credentials = json.loads(base64.urlsafe_b64decode(os.environ['HUB_CREDENTIALS']))
            self.docker_client.login(
                username=credentials['Username'], password=credentials['Password']
            )

    def build_images(self, repository, files):
        print("Building release images...")
        git_sha = repository.write_git_sha()
        compose_image_base_name = "docker/compose"
        print('Building {image} image (alpine based)'.format(image=compose_image_base_name))
        logstream = self.docker_client.build(
            REPO_ROOT,
            tag='{image_base_image}:{version}'.format(
                image_base_image=compose_image_base_name,
                version=self.version
            ),
            buildargs={
                'GIT_COMMIT': git_sha,
            },
            target='build',
            decode=True
        )
        for chunk in logstream:
            if 'error' in chunk:
                raise ScriptError('Build error: {}'.format(chunk['error']))
            if 'stream' in chunk:
                print(chunk['stream'], end='')

        if self.latest:
            self.docker_client.tag(
                '{image}:{tag}'.format(image=compose_image_base_name, tag=self.version),
                '{image}:{tag}'.format(image=compose_image_base_name, tag='latest')
            )

        print('Building test image (debian based for UCP e2e)')
        compose_tests_image_base_name = compose_image_base_name + '-tests'
        ucp_test_image = '{image}:{tag}'.format(image=compose_tests_image_base_name, tag=self.version)
        logstream = self.docker_client.build(
            REPO_ROOT,
            tag=ucp_test_image,
            target='build',
            buildargs={
                'BUILD_PLATFORM': 'debian',
                'GIT_COMMIT': git_sha,
            },
            decode=True
        )
        for chunk in logstream:
            if 'error' in chunk:
                raise ScriptError('Build error: {}'.format(chunk['error']))
            if 'stream' in chunk:
                print(chunk['stream'], end='')

        self.docker_client.tag(
            '{image}:{tag}'.format(image=compose_tests_image_base_name, tag=self.version),
            '{image}:{tag}'.format(image=compose_tests_image_base_name, tag='latest')
        )

    @property
    def image_names(self):
        images = [
            'docker/compose-tests:latest',
            'docker/compose-tests:{}'.format(self.version),
            'docker/compose:{}'.format(self.version)
        ]
        if self.latest:
            images.append('docker/compose:latest')
        return images

    def check_images(self):
        for name in self.image_names:
            try:
                self.docker_client.inspect_image(name)
            except docker.errors.ImageNotFound:
                print('Expected image {} was not found'.format(name))
                return False
        return True

    def push_images(self):
        for name in self.image_names:
            print('Pushing {} to Docker Hub'.format(name))
            logstream = self.docker_client.push(name, stream=True, decode=True)
            for chunk in logstream:
                if 'status' in chunk:
                    print(chunk['status'])
                if 'error' in chunk:
                    raise ScriptError(
                        'Error pushing {name}: {err}'.format(name=name, err=chunk['error'])
                    )
