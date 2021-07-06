# Kubernetes 

This directory holds everything to start a local Kubernetes cluster running: 
- the ASR worker
- the ASR API
- DANE server
- RabbitMQ server


# References

- [How to use local Docker images](https://medium.com/bb-tutorials-and-thoughts/how-to-use-own-local-doker-images-with-minikube-2c1ed0b0968)
- [How to hookup external services](https://www.youtube.com/watch?v=fvpq4jqtuZ8) (useful for Elasticsearch!)


https://requires.io

https://www.sonarqube.org/

https://pypi.org/project/bandit/

http://w3af.org


```
kubectl create configmap dane-asr-worker-cfg --from-file [DANE-ASR-WORKER-HOME]/config.yml
```


Force stopping a POD that won't terminate:

```
kubectl delete pod <PODNAME> --grace-period=0 --force --namespace <NAMESPACE>
```