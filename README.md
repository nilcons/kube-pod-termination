# Investigations around Kubernetes Pod Termination

Date: 2024-04-24, newest Azure released Kubernetes is 1.29.

## Questions

1. Does a terminating pod immediately become not ready and is it removed from the endpoints?

2. How `pod.spec.containers.lifecycle.preStop` behaves with `pod.spec.terminationGracePeriodSeconds`?

3. When is a `SIGTERM` delivered with `preStop`?

## Answer 1: termination and readiness

We say, that a pod is under termination if the `metadata.deletionTimestamp` is in the past.

A pod stays ready no matter it's current termination status, you can check this with `kubectl get pod -o yaml <podname>`.

But, the endpoints (that is backing the services) have built-in extra logic to remove terminating pods.

This extra logic was always there, according to the documentation, so even with older versions of Kubernetes, you don't have to hack with readiness probes and your application code, just to get the correct termination behavior.

In newer versions of kubernetes (starting around 1.21), the state can also be explicitly queried by referring to EndpointSlices, as documented in https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/

Pay attention to the fact, that in the `EndpointSlices` terminology `endpoints.conditions.serving` has the boolean that is representing readiness, and `endpoints.conditions.ready` is a boolean that is saying if the endpoint is being included in the service (e.g. if it's serving).  Yes, the terminology is inverted compared to meaning...

All this means, that after an application receives a `SIGTERM` signal, it can kinda assume, that no more requests will arrive (depending on speed of kube-proxy) after a couple of seconds, and it can exit once there all current requests finished serving.

## Answer 2: the `preStop` idea and the compatibility with `terminationGracePeriodSeconds`

As it's not always easy to modify legacy applications, and sometimes no behavior is implemented for `SIGTERM` at all (e.g. the app just dies), it's useful to know about `preStop`.

With `preStop` one can specify a command (usual idea is `sleep 15`), that is always executed before sending the `SIGTERM`.

The documentation says, that this extra execution time is not added into the grace period as extra, the grace period still starts at the `deletionTimestamp`, and once the grace period is up, the `SIGKILL` will be sent no matter what.

But the documentation is incorrect in multiple ways:

  - in version 1.27 and below, the implementation was incorrect, and the `preStop` execution time was actually not measured into the grace period, so in the example of `sleep 15`, you won the extra 15 seconds,
  - even in this version, it's true, that if the `preStop` command tries to execute for longer than the grace period, then the `preStop` is killed, and then the container is also killed with `SIGTERM` (and 1-2 seconds after `SIGKILL`),
  - after the fix landing in 1.28, the behavior is as documented, except that there is an undocumented 1-2 seconds extra grace between finish of `preStop` and container killing.  As soon as `preStop` finishes (even if after deadline), a `SIGTERM` is sent, and after 1-2 seconds a `SIGKILL`.

All this can be tested with the attached `deployment.yaml`, and the python example program.

Many blog articles advise you to use `preStop` with `sleep 15`, to make sure that the apps have time to finish, this advice is correct, but depends on the `sleep` executable being available in the container.

Many "secure" scratch based images do not have any executables, not even `sleep`, so to support these, v1.30 will have a built-in sleep feature for `lifeCycle.preStop`, we will have to see the `SIGTERM` behavior with it.

## Answer 3: when is the `SIGTERM` delivered with `preStop`?

So far, in all cases, the `SIGTERM` is not sent while `preStop` is still executing.  So if your main issue is that your legacy app doesn't handle signals AT ALL, and you just want to delay, so current requests can finish, then the `sleep 15` trick can work.

I think these tricks will become less and less effective, if the HTTP TCP connection exists directly between the app and the pod, as modern browsers and web servers keep the connection open.  And keeping the connection open is definitely becoming the default once we are talking about HTTP 2 or 3, or other modern protocols.

This is one more reason to use some kind of an ingress always (maybe even inside the cluster), and to double check that the ingress doesn't keep connections open, or if it does, then check that it has logic to notice `EndpointSlices` updates.

## Bonus confusion: `deployment.spec.minReadySeconds` vs `pod.spec.lifecycle.postStart`

If your worry is that during rolling updates, your legacy app doesn't have a readiness endpoint, or it has, but you are too lazy to write a `readinessProbe`, then some people recommend using `deployment.spec.minReadySeconds`.

This is not correct advice, because this flag is there as a safety against incorrect updates rolling quickly to the whole deployment, including all replicas.

The use case for this flag, is to handle new versions of apps, that seem to start, but they crash during initialization, let's say in the first 60 seconds, and then you can set this flag to 90 or something.

You can also use `deployment.spec.minReadySeconds` if you just want to artificially slow down rolling updates for some reason.

The problem is, that even during this waiting time, the app is eligible to become ready and to be added to endpoints.

One can also see, that this option has nothing to do with readiness, from the location of the flag, it's in `Deployment` manifests, not in `Pod` manifests.

If you want to add extra waiting time for your app, without adding readiness probes, you can use `pod.spec.lifecycle.postStart`, which has the behavior that you need: pod status will not even say Running, before the command is finished, and pods during `postStart` are never added to endpoints.

## Credits

All investigation by Gergely Risko, motivation from learnk8s: https://learnk8s.io/graceful-shutdown
