#!/bin/bash
cd /var/apps/paycor
git stash
git pull origin main
uv sync
