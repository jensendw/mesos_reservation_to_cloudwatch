FROM python:2.7.11-onbuild
CMD [ "python", "./mesos_reservation_cloudwatch_metrics.py" ]
