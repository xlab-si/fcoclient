# Copyright (c) 2017 XLAB d.o.o.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Command line interface for FCO client.
"""

from __future__ import print_function

import argparse
import inspect
import json
import logging
import sys

from fcoclient.client import Client


def _configure_logging():
    fmt_stream = logging.Formatter("[%(levelname)s] - %(message)s")
    handler_stream = logging.StreamHandler()
    handler_stream.setFormatter(fmt_stream)
    handler_stream.setLevel(logging.INFO)

    fmt_file = logging.Formatter(
        "%(asctime)s %(name)s:%(lineno)s [%(levelname)s] - %(message)s"
    )
    handler_file = logging.FileHandler(".fco.log")
    handler_file.setFormatter(fmt_file)
    handler_file.setLevel(logging.DEBUG)

    log = logging.getLogger("fcoclient")
    log.addHandler(handler_stream)
    log.addHandler(handler_file)
    log.setLevel(logging.DEBUG)

    return log


def fail(msg, *args):
    LOGGER.error(msg.format(*args))
    sys.exit(1)


def display(item):
    print(json.dumps(item, indent=2))


class ArgParser(argparse.ArgumentParser):
    """
    Argument parser that displays help on error
    """

    def error(self, message):
        sys.stderr.write("error: {}\n".format(message))
        self.print_help()
        sys.exit(2)

    def add_subparsers(self):
        # Workaround for http://bugs.python.org/issue9253
        subparsers = super(ArgParser, self).add_subparsers()
        subparsers.required = True
        subparsers.dest = "command"
        return subparsers


class Config(dict):

    valid_keys = {"url", "username", "customer", "password", "verify"}

    def __init__(self, data=None, **rest):
        invalid = [k for k in data.keys() if k not in self.valid_keys]
        if len(invalid) != 0:
            fail("Invalid settings key(s) found: {}", ",".join(invalid))

        if data is None:
            data = rest
        else:
            data.update(rest)
        # TODO: Fix this as soon as possible!!!
        data["verify"] = False
        super(Config, self).__init__(data)

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self, f, indent=2)

    # Construction helper
    @staticmethod
    def load_from_file(path, fail_on_missing=True):
        try:
            with open(path) as f:
                data = json.load(f)
        except IOError:
            if fail_on_missing:
                fail("File {} is missing", path)
            data = {}  # Missing file simply means no settings are present yet
        except:
            fail("File {} is not valid JSON", path)
        return Config(data)


class Command(object):

    @staticmethod
    def add_subparser(subparsers):
        raise NotImplementedError("Command is an abstract class")

    def __init__(self, config_path):
        self.client = Client(**Config.load_from_file(config_path))


class Configure(Command):

    @staticmethod
    def add_subparser(subparsers):
        parser = subparsers.add_parser("configure", help="Configure client")
        parser.add_argument("url", help="FCO URL")
        parser.add_argument("username", help="FCO username")
        parser.add_argument("customer", help="FCO customer")
        parser.add_argument("password", help="FCO password")
        return parser

    def __init__(self, config_path):
        pass  # Prevent client from being constructed

    def configure(self, args):
        LOGGER.info("Configuring client")
        config = Config.load_from_file(args.config, fail_on_missing=False)
        config["url"] = args.url
        config["username"] = args.username
        config["customer"] = args.customer
        config["password"] = args.password
        config.save(args.config)
        LOGGER.info("Client configured")


class Offer(Command):

    @staticmethod
    def add_subparser(subparsers):
        parser = subparsers.add_parser("offer", help="Inspect product offers")
        subs = parser.add_subparsers()

        sub = subs.add_parser("list", help="List product offers")
        sub.add_argument("-n", "--no-items", type=int, default=100,
                         help="Numbr of offers to display")
        sub.add_argument("-t", "--type",
                         help="Only display offers for associated type")

        sub = subs.add_parser("get", help="Get details about selected offer")
        sub.add_argument("uuid", help="Offer UUID")

        return parser

    def list(self, args):
        LOGGER.info("Listing product offers")
        conditions = {}
        if args.type is not None:
            conditions["productAssociatedType"] = args.type
        for po in self.client.product_offer.list(args.no_items, **conditions):
            print("{}: {} ({})".format(po["productAssociatedType"], po.name,
                                       po.uuid))
        LOGGER.info("Offers listed")

    def get(self, args):
        LOGGER.info("Getting product offer details")
        display(self.client.product_offer.get(uuid=args.uuid))
        LOGGER.info("Product offer details retrieved")


def create_parser():
    def is_command(item):
        return (inspect.isclass(item) and item != Command and
                issubclass(item, Command))

    parser = ArgParser(description="DICE Deployment Service CLI",
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--config", help="Configuration file to use",
                        default=".fco.conf")
    subparsers = parser.add_subparsers()

    commands = inspect.getmembers(sys.modules[__name__], is_command)
    for _, cls in commands:
        sub = cls.add_subparser(subparsers)
        sub.set_defaults(cls=cls)

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    getattr(args.cls(args.config), args.command)(args)


LOGGER = _configure_logging()