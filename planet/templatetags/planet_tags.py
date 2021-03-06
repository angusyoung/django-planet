#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Several useful template tags!
"""

import re
from datetime import datetime, timedelta

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.template import TemplateSyntaxError, Node, loader, Variable
from django.utils.translation import ugettext as _
from django.utils.text import smart_split
from django.conf import settings

from planet.models import Author, Feed, Post

from tagging.models import Tag, TaggedItem


register = template.Library()


@register.inclusion_tag('planet/authors/blocks/list_for_tag.html')
def authors_about(tag):
    """
    Displays a list of authors who have been written a post tagged with this tag.    
    """
    post_ids = TaggedItem.objects.get_by_model(
        Post.site_objects, tag).values_list("id", flat=True)
    
    authors = Author.site_objects.filter(post__in=post_ids).distinct()

    return {"authors": authors, "tag": tag}


@register.inclusion_tag('planet/feeds/blocks/list_for_tag.html')
def feeds_about(tag):
    """
    Displays a list of feeds whose posts have been tagged with this tag.
    """
    post_ids = TaggedItem.objects.get_by_model(
        Post.site_objects, tag).values_list("id", flat=True)
    
    feeds_list = Feed.site_objects.filter(post__in=post_ids).distinct()

    return {"feeds_list": feeds_list, "tag": tag}


@register.inclusion_tag("planet/tags/blocks/related_list.html")
def related_tags_for(tag, count=20):
    """
    Displays a list of tags that have been used for tagging Posts instances
    always that <tag> have been used too.
    """
    related_tags = Tag.objects.related_for_model([tag], Post, counts=True)

    return {"related_tags": related_tags[:count]}


@register.inclusion_tag("planet/dummy.html", takes_context=True)
def post_details(context, post, template="planet/posts/details.html"):
    """
    Displays info about a post: title, date, feed and tags.
    """
    context.update({"template": template, "post": post})
    return context


@register.inclusion_tag("planet/posts/full_details.html")
def post_full_details(post):
    """
    Displays full info about a post: title, date, feed, authors and tags,
    and it also displays external links to post and blog.
    """
    return {"post": post}


@register.inclusion_tag("planet/tags/blocks/feeds_cloud.html")
def cloud_for_feed(feed, min_count=3):
    """
    Displays a tag cloud for a given feed object.    
    """
    tags_cloud = Tag.objects.cloud_for_model(
        Post, filters={"feed": feed}, min_count=min_count)

    return {"tags_cloud": tags_cloud, "feed": feed}


@register.inclusion_tag("planet/tags/blocks/authors_cloud.html")
def cloud_for_author(author, min_count=3):
    """
    Displays a tag cloud for a given author object.    
    """
    tags_cloud = Tag.objects.cloud_for_model(
        Post, filters={"authors": author}, min_count=min_count)

    return {"tags_cloud": tags_cloud, "author": author}


@register.inclusion_tag("planet/tags/blocks/blogs_cloud.html")
def cloud_for_blog(blog, min_count=3):
    """
    Displays a tag cloud for a given blog object.    
    """
    tags_cloud = Tag.objects.cloud_for_model(
        Post, filters={"feed__blog": blog}, min_count=min_count)

    return {"tags_cloud": tags_cloud, "blog": blog}


@register.inclusion_tag("planet/authors/blocks/list_for_feed.html")
def authors_for_feed(feed):

    authors = Author.site_objects.filter(post__feed=feed)

    return {"authors": authors, "feed": feed}


@register.inclusion_tag("planet/feeds/blocks/list_for_author.html")
def feeds_for_author(author):
    
    feeds = Feed.site_objects.filter(
        post__authors=author).order_by("title").distinct()

    return {"feeds_list": feeds, "author": author}


class PlanetPostList(Node):
    def __init__(self, limit=None, tag=None, category=None, template=None,
            hidden=None, days=None, page=None):
        self.limit = limit
        self.tag = tag
        self.category = category
        self.template = template
        self.hidden = hidden
        self.days = days
        self.page = page

    def resolve(self, context, vars):
        """
        Resolve all the template variables listed in vars through the given
        context
        """
        for var in vars:
            val_var = self.__getattribute__(var)
            if val_var is not None:
                self.__setattr__(var, Variable(val_var).resolve(context))

    def process(self, context):
        self.resolve(context, ('tag', 'category', 'template', 'limit',
                               'hidden', 'days', 'page'))
        if self.hidden is not None and self.hidden:
            posts = Post.objects.filter(feed__site=settings.SITE_ID)
        else:
            posts = Post.site_objects
        if self.tag is not None:
            posts = TaggedItem.objects.get_by_model(posts, self.tag)

        #select also related objects, in this way we avoid future queries to
        #retrieve for example the blog name
        posts = posts.select_related()

        if self.category is not None:
            posts = posts.filter(feed__category__title=self.category)

        ##TODO: test under mysql and sqlite

        if self.page is None:
            self.page = 0
        else:
            self.page = int(self.page)

        if self.limit is None or not self.limit:
            self.limit = 200

        if self.days is not None:
            self.days = int(self.days)

            # we go back in time, so start_date > (wanted posts) > end_date
            start_date = datetime.today()
            if self.page > 0:
                start_date = start_date - timedelta(days=self.page*self.days)
            end_date = start_date - timedelta(days=self.days)

            posts = posts.extra(
                select={
                    'date':
                    "COALESCE(planet_post.date_modified, planet_post.date_created)"
                },
                order_by=['-date'],
                where=['COALESCE(planet_post.date_modified, planet_post.date_created) > %s AND COALESCE(planet_post.date_modified, planet_post.date_created) < %s'],
                params=[end_date, start_date],
            )
        else:
            posts = posts.extra(
                select={
                    'date':
                    "COALESCE(planet_post.date_modified, planet_post.date_created)"
                },
                order_by=['-date']
            )

        posts = posts[:self.limit]

        context['posts'] = posts

        if self.template is None:
            self.template = "planet/list.html"
        
        return (self.template, context)

    def render(self, context):
        template, context = self.process(context)
        return loader.get_template(template).render(context)


@register.tag()
def planet_post_list(__, token):
    """
    Render a list of posts using the planet/list.html template.

    Params:
        limit: limit to this number of entries
        tag: select only Posts that matches this tag
        category: select only Posts that belongs to Feeds under this Category
        template: render using a different template
        hidden: show also hidden posts

    Examples:
        {% planet_post_list with limit=10 tag=tag %}
        {% planet_post_list with tag="Redis" %}
        {% planet_post_list with category="PyPy" hidden="True" %}
    """
    bits = list(smart_split(token.contents))
    len_bits = len(bits)
    kwargs = {}
    if len_bits > 1:
        if bits[1] != 'with':
            raise TemplateSyntaxError(_("if given, fourth argument to %s tag must be 'with'") % bits[0])
        for i in range(2, len_bits):
            try:
                name, value = bits[i].split('=')
                if name in ('tag', 'category', 'template', 'limit', 'hidden',
                            'days', 'page'):
                    kwargs[str(name)] = value
                else:
                    raise TemplateSyntaxError(_("%(tag)s tag was given an invalid option: '%(option)s'") % {
                        'tag': bits[0],
                        'option': name,
                    })
            except ValueError:
                raise TemplateSyntaxError(_("%(tag)s tag was given a badly formatted option: '%(option)s'") % {
                    'tag': bits[0],
                    'option': bits[i],
                })

    return PlanetPostList(**kwargs)


@register.filter
@stringfilter
def clean_html(html):
    pattern_list = ('(style=".*?")', '(<style.*?</style>")',
        '(<script.*?</script>")', )
    for pattern in pattern_list:
        html = re.sub(pattern, '', html)

    pattern_list = (('(<br.?/>){3,}', '<br/><br/>'), )
    for (pattern, replacement) in pattern_list:
        html = re.sub(pattern, replacement, html)
    return mark_safe(html)