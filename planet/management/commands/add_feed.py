#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from optparse import make_option
from django.core.management.base import BaseCommand

from planet.management.commands import process_feed


class Command(BaseCommand):
    help = "Add a complete blog feed to our db."
    args = "<feed_url>"
    option_list = BaseCommand.option_list + (
        make_option('-c', '--category',
            action='store',
            dest='category',
            default=None,
            metavar='Title',
            help='Add this feed to a Category'),
        )

    def handle(self, *args, **options):
        plogger = logging.getLogger('PlanetLogger')
        plogger.info("Add feed")
        if not len(args):
            plogger.error("You must provide the feed url as parameter")
            exit(0)

        feed_url = args[0]
        # process feed in create-mode
        process_feed(feed_url, create=True, category_title=options['category'])
                