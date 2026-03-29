FROM python:3.12 AS python-build

RUN pip install --upgrade pip

RUN addgroup admin && adduser admin --ingroup admin
RUN chown -R admin:admin /home/admin/
USER admin
COPY --chown=admin:admin ./app /home/admin/app
RUN pip install -r /home/admin/app/requirements.pip

FROM python:3.12-slim-bookworm
RUN pip install --upgrade pip setuptools
RUN addgroup admin && adduser admin --ingroup admin
RUN chown -R admin:admin /home/admin/
COPY --from=python-build --chown=admin:admin /home/admin /home/admin

RUN apt-get update && \
    apt-get install -y \
        locales && \
    rm -r /var/lib/apt/lists/*


RUN apt update
RUN apt-get install -y mariadb-client libmariadb3 mariadb-common

RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    sed -i -e 's/# es_MX.UTF-8 UTF-8/es_MX.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales

ENV PATH="/home/admin/.local/bin:${PATH}"

WORKDIR /home/admin/app

USER admin

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000", "--limit-concurrency", "300", "--timeout-keep-alive", "35", "--header", "Strict-Transport-Security:max-age=31536000;includeSubDomains", "--no-server-header"]
