#!/bin/bash
celery -A tasks worker -l INFO -Q celery --prefetch-multiplier=1 --autoscale=16,1