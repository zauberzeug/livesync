FROM python:3.7

RUN apt update && apt install -y \
    rsync \ 
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt /livesync/
WORKDIR /livesync

RUN mkdir -p /root/.ssh && \
echo '-----BEGIN OPENSSH PRIVATE KEY-----\n\
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\n\
QyNTUxOQAAACBgQkCwBpNRzd3pQ4TYTrSI1y11y1l3ay/pCv+4cedxwwAAAJg/9pNIP/aT\n\
SAAAAAtzc2gtZWQyNTUxOQAAACBgQkCwBpNRzd3pQ4TYTrSI1y11y1l3ay/pCv+4cedxww\n\
AAAEAkwnTl5j6SNfDsAUj4D+D2WWsOCNMGVgxDQifyVYXFyGBCQLAGk1HN3elDhNhOtIjX\n\
LXXLWXdrL+kK/7hx53HDAAAAFHJvZGphQFJvZGphLU0xLmxvY2FsAQ==\n\
-----END OPENSSH PRIVATE KEY-----' >> /root/.ssh/id_ed25519 && \
chmod 600 /root/.ssh/id_ed25519 && \
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGBCQLAGk1HN3elDhNhOtIjXLXXLWXdrL+kK/7hx53HD livesync.docker\n' > /root/.ssh/id_ed25519.pub && \
echo "Host target\n   StrictHostKeyChecking no\n   UserKnownHostsFile=/dev/null\n   LogLevel=ERROR\n" >> /root/.ssh/config

RUN wget https://raw.githubusercontent.com/torokmark/assert.sh/main/assert.sh -O /root/assert.sh && echo ". /root/assert.sh" >> ~/.bashrc

WORKDIR /livesync
ADD livesync /livesync/livesync
COPY setup.py LICENSE README.md /livesync/
RUN pip install -e . --no-cache-dir
ADD tests /livesync/tests

WORKDIR /app
ENTRYPOINT [ "livesync" ]
CMD [ "--help" ]