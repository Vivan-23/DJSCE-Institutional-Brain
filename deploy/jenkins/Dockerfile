# Jenkins for the hosted VM: Docker CLI + compose (talks to the host daemon via the socket), rsync, curl,
# and the plugins the configuration in casc.yaml needs. No setup wizard; casc.yaml configures everything.
FROM docker:cli AS dockercli

FROM jenkins/jenkins:lts-jdk21
USER root
RUN apt-get update && apt-get install -y --no-install-recommends rsync curl && rm -rf /var/lib/apt/lists/*
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
USER jenkins
RUN jenkins-plugin-cli --plugins configuration-as-code job-dsl workflow-aggregator git github ssh-credentials plain-credentials
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false -Xmx768m"
ENV CASC_JENKINS_CONFIG=/var/jenkins_home/casc.yaml
