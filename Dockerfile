# Build like this:
#   docker build -t ttl.sh/kube-pod-term-test:1h
#   docker build -t ttl.sh/kube-pod-term-test:2h
#   docker push ttl.sh/kube-pod-term-test:1h
#   docker push ttl.sh/kube-pod-term-test:2h
# And then you can test rolling updates by switching between these two.

FROM nilcons/debian

COPY test.py /
CMD ["/test.py"]
