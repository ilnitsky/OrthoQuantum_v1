FROM buildpack-deps:buster as suexec-builder
COPY ./su-exec /su-exec
RUN cd /su-exec && make



FROM ncbi/blast:2.11.0

RUN curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -

#### Following is copy of python:3.9.5-slim dockerfile

# ensure local python is preferred over distribution python
ENV PATH /usr/local/bin:$PATH

# http://bugs.python.org/issue19846
# > At the moment, setting "LANG=C" on a Linux system *fundamentally breaks Python 3*, and that's not OK.
ENV LANG C.UTF-8

# runtime dependencies
RUN set -eux; \
	apt-get update; \
	apt-get install -y --no-install-recommends \
		ca-certificates \
		netbase \
		tzdata \
	; \
	rm -rf /var/lib/apt/lists/*

ENV GPG_KEY E3FF2839C048B25C084DEBE9B26995E310250568
ENV PYTHON_VERSION 3.9.5

RUN set -ex \
	\
	&& savedAptMark="$(apt-mark showmanual)" \
	&& apt-get update && apt-get install -y --no-install-recommends \
		dpkg-dev \
		gcc \
		libbluetooth-dev \
		libbz2-dev \
		libc6-dev \
		libexpat1-dev \
		libffi-dev \
		libgdbm-dev \
		liblzma-dev \
		libncursesw5-dev \
		libreadline-dev \
		libsqlite3-dev \
		libssl-dev \
		make \
		tk-dev \
		uuid-dev \
		wget \
		xz-utils \
		zlib1g-dev \
# as of Stretch, "gpg" is no longer included by default
		$(command -v gpg > /dev/null || echo 'gnupg dirmngr') \
	\
	&& wget -O python.tar.xz "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz" \
	&& wget -O python.tar.xz.asc "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz.asc" \
	&& export GNUPGHOME="$(mktemp -d)" \
	&& gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys "$GPG_KEY" \
	&& gpg --batch --verify python.tar.xz.asc python.tar.xz \
	&& { command -v gpgconf > /dev/null && gpgconf --kill all || :; } \
	&& rm -rf "$GNUPGHOME" python.tar.xz.asc \
	&& mkdir -p /usr/src/python \
	&& tar -xJC /usr/src/python --strip-components=1 -f python.tar.xz \
	&& rm python.tar.xz \
	\
	&& cd /usr/src/python \
	&& gnuArch="$(dpkg-architecture --query DEB_BUILD_GNU_TYPE)" \
	&& ./configure \
		--build="$gnuArch" \
		--enable-loadable-sqlite-extensions \
		--enable-optimizations \
		--enable-option-checking=fatal \
		--enable-shared \
		--with-system-expat \
		--with-system-ffi \
		--without-ensurepip \
	&& make -j "$(nproc)" \
		LDFLAGS="-Wl,--strip-all" \
	&& make install \
	&& cd / \
	&& rm -rf /usr/src/python \
	\
	&& find /usr/local -depth \
		\( \
			\( -type d -a \( -name test -o -name tests -o -name idle_test \) \) \
			-o \( -type f -a \( -name '*.pyc' -o -name '*.pyo' -o -name '*.a' \) \) \
		\) -exec rm -rf '{}' + \
	\
	&& ldconfig \
	\
	&& apt-mark auto '.*' > /dev/null \
	&& apt-mark manual $savedAptMark \
	&& find /usr/local -type f -executable -not \( -name '*tkinter*' \) -exec ldd '{}' ';' \
		| awk '/=>/ { print $(NF-1) }' \
		| sort -u \
		| xargs -r dpkg-query --search \
		| cut -d: -f1 \
		| sort -u \
		| xargs -r apt-mark manual \
	&& apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
	&& rm -rf /var/lib/apt/lists/* \
	\
	&& python3 --version

# make some useful symlinks that are expected to exist
RUN cd /usr/local/bin \
	&& ln -s idle3 idle \
	&& ln -s pydoc3 pydoc \
	&& ln -s python3 python \
	&& ln -s python3-config python-config

# if this is called "PIP_VERSION", pip explodes with "ValueError: invalid truth value '<VERSION>'"
ENV PYTHON_PIP_VERSION 21.1.2
# https://github.com/pypa/get-pip
ENV PYTHON_GET_PIP_URL https://github.com/pypa/get-pip/raw/936e08ce004d0b2fae8952c50f7ccce1bc578ce5/public/get-pip.py
ENV PYTHON_GET_PIP_SHA256 8890955d56a8262348470a76dc432825f61a84a54e2985a86cd520f656a6e220

RUN set -ex; \
	\
	savedAptMark="$(apt-mark showmanual)"; \
	apt-get update; \
	apt-get install -y --no-install-recommends wget; \
	\
	wget -O get-pip.py "$PYTHON_GET_PIP_URL"; \
	echo "$PYTHON_GET_PIP_SHA256 *get-pip.py" | sha256sum --check --strict -; \
	\
	apt-mark auto '.*' > /dev/null; \
	[ -z "$savedAptMark" ] || apt-mark manual $savedAptMark; \
	apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false; \
	rm -rf /var/lib/apt/lists/*; \
	\
	python get-pip.py \
		--disable-pip-version-check \
		--no-cache-dir \
		"pip==$PYTHON_PIP_VERSION" \
	; \
	pip --version; \
	\
	find /usr/local -depth \
		\( \
			\( -type d -a \( -name test -o -name tests -o -name idle_test \) \) \
			-o \
			\( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
		\) -exec rm -rf '{}' +; \
	rm -f get-pip.py


#### At this point we have ncbi/blast + python:3.9.5-slim

ARG DEBUG=""
ENV DEBUG=${DEBUG}

RUN useradd -ms /bin/bash -u 1234 www                             &&\
    apt-get update                                                &&\
    apt-get upgrade -y                                            &&\
    apt-get install -y --no-install-recommends                      \
            ca-certificates build-essential                         \
			chromium                                                \
			# chromium dependencies
			gconf-service libasound2 libatk1.0-0 libc6 libcairo2    \
			libcups2 libdbus-1-3 libexpat1 libfontconfig1 libgcc1   \
			libgconf-2-4 libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 \
			libnspr4 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6  \
			libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 \
			libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2       \
			libxrender1 libxss1 libxtst6 fonts-liberation           \
			libappindicator1 libnss3 lsb-release xdg-utils wget   &&\
    python3 -m pip --no-cache-dir install --upgrade pip pipenv    &&\
    rm -rf /var/lib/apt/lists/*                                   &&\
    rm -rf /usr/share/doc                                         &&\
    rm -rf /usr/share/man                                         &&\
    apt-get clean

ENV PATH /home/www/.local/bin:$PATH

COPY --from=suexec-builder --chown=root:root /su-exec/su-exec /bin/su-exec

WORKDIR /app/

# Installing dependencies separately in order to take advantage of docker caching mechanism
COPY --chown=www:www ./app/Pipfile* /app/
RUN su www -c "pipenv install --deploy --system --clear"

COPY --chown=www:www ./app/ /app/

# entrypoint.sh drops the priveleges as soon as it
# ensures correct permissions on everything
ENTRYPOINT [ "/app/entrypoint.sh" ]
