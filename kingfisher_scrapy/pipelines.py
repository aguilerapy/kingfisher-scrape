# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html

import os
import json
import hashlib
import requests
import urllib.parse

from scrapy.pipelines.files import FilesPipeline
from scrapy.utils.python import to_bytes
from scrapy.exceptions import DropItem, NotConfigured
from scrapy.http import Request


class KingfisherFilesPipeline(FilesPipeline):

    def _get_start_time(self, spider):
        stats = spider.crawler.stats.get_stats()
        start_time = stats.get("start_time")
        return start_time

    def file_path(self, request, response=None, info=None):
        start_time = self._get_start_time(info.spider)
        start_time_str = start_time.strftime("%Y%m%d_%H%M%S")

        url = request.url
        media_guid = hashlib.sha1(to_bytes(url)).hexdigest()
        media_ext = os.path.splitext(url)[1]

        if not media_ext:
            media_ext = '.json'
        # Put files in a directory named after the scraper they came from, and the scraper starttime
        return '%s/%s/%s%s' % (info.spider.name, start_time_str, media_guid, media_ext)

    def item_completed(self, results, item, info):

        """
        This is triggered when a JSON file has finished downloading.
        """

        if hasattr(info.spider, 'sample')  and info.spider.sample == 'true':
            is_sample = 1
        else:
            is_sample = 0
        
        files_store = info.spider.crawler.settings.get("FILES_STORE")

        completed_files = []

        for ok, file_data in results:
            if ok:
                file_url = file_data.get("url")
                local_path = os.path.join(files_store, file_data.get("path"))

                start_time = self._get_start_time(info.spider)

                item_data = {
                    "collection_source": info.spider.name,
                    "collection_data_version": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "collection_sample": is_sample,
                    "file_name": local_path,
                    "file_url": file_url,
                    "file_data_type": item.get("data_type"),
                    "file_encoding": "utf-8",
                    "local_path": local_path
                }

                completed_files.append(item_data)

        return completed_files


class KingfisherPostPipeline(object):

    def __init__(self, crawler):
        self.crawler = crawler
        self.api_url = self._build_api_url(crawler)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def _build_api_url(self, crawler):
        api_uri = crawler.settings['KINGFISHER_API_FILE_URI']
        api_item_uri = crawler.settings['KINGFISHER_API_ITEM_URI']
        api_key = crawler.settings['KINGFISHER_API_KEY']

        if api_uri is None or api_item_uri is None or api_key is None:
            raise NotConfigured('Kingfisher API not configured.')

        # TODO: figure out which api endpoint based on the data_type OR probably metadata passed from the spider

        headers = {"Authorization": "ApiKey " + api_key}
        return api_uri, headers

    def process_item(self, item, spider):
        url, headers = self.api_url
        for completed in item:
            
            local_path = completed.get("local_path")
            with open(local_path) as json_file:
                json_from_file = json.load(json_file)

            completed['data'] = json_from_file

            headers['Content-Type'] = 'application/json'

            post_request = Request(
                url=url,
                method='POST',
                body=json.dumps(completed),
                headers=headers
            )
            self.crawler.engine.crawl(post_request, spider)
        
        raise DropItem("Items posted..")
