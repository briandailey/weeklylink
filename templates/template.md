---
title: Weekly Assorted Things
description: A periodic post of things I found interesting.
slug: weekly-assorted-things-{{ date.strftime("%Y-%m-%d") }}
date: {{ date.strftime("%Y-%m-%d") }}
categories:
    - Assorted
tags:
    - Links
---


{% for item in items %}
1. [{{ item.title }}]({{ item.link }}){% if item.summary %}\
  {{ item.summary }}{% endif %}{% endfor %}
