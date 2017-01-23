Mesos Reservation to cloudwatch

# Overview

This script transmits the reservation metrics that the Mesos agent provides to AWS cloudwatch.  It is designed to be ran on Mesos agents that are part of an autoscaling group.

# Setup

This docker container only takes one environment variable as an override.

* CONTAINERS_URL
  *  This is the URL that you want to retrieve the container metrics from.
  * Default value is http://localhost:5051/containers which should suffice in most instances.

# Deployment

I run this container once a minute on every mesos slave in order to transmit the reservation metrics to cloudwatch.  This allows me to autoscale my ASG based on the reservations used instead of the actual resource consumption.  I typically run the container in the following manner:

```shell
docker run --rm jensendw/mesos_reservation_to_cloudwatch 
```
