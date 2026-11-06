#!/usr/bin/env bash
# Prepare the host for a LibreOffice build. Installs dependencies, creates the
# build tree, and reports whether the machine is adequate.
#
# It does NOT clone the source and does NOT compile anything.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
BUILD=${LO_BUILD:-$REPO/build}

echo "== machine =="
cpus=$(nproc)
mem_gb=$(awk '/MemTotal/{printf "%d", $2/1024/1024}' /proc/meminfo)
free_gb=$(df -BG --output=avail "$(dirname "$BUILD")" | tail -1 | tr -dc '0-9')
echo "cores: $cpus   ram: ${mem_gb}G   free disk: ${free_gb}G"

verdict=ok
[ "$mem_gb" -ge 16 ] || { echo "WARN: under 16G RAM, linking will swap"; verdict=risky; }
[ "$free_gb" -ge 40 ] || { echo "WARN: under 40G free, a source tree plus objects will not fit"; verdict=risky; }
echo "verdict: $verdict"

echo "== packages =="
PKGS="gcc gcc-c++ make autoconf automake bison flex gperf pkgconf-pkg-config \
git curl wget which perl-core python3-devel zip unzip ccache \
patch libtool perl-Archive-Zip meson ninja-build \
fontconfig-devel freetype-devel libX11-devel libXext-devel libXrender-devel \
libICE-devel libSM-devel cups-devel dbus-devel expat-devel \
libjpeg-turbo-devel libpng-devel libxml2-devel libxslt-devel \
openssl-devel zlib-devel ncurses-devel libcurl-devel \
gtk3-devel cairo-devel pango-devel gdk-pixbuf2-devel \
nss-devel nspr-devel \
libXinerama-devel libXrandr-devel libXfixes-devel"

failed=""
for pkg in $PKGS; do
  rpm -q "$pkg" >/dev/null 2>&1 && continue
  sudo -n dnf install -y "$pkg" >/tmp/dnf-one.log 2>&1 || failed="$failed $pkg"
done

if [ -n "$failed" ]; then
  echo "could not install:$failed"
  echo "  (some may not exist under that name on this distribution)"
else
  echo "all listed packages present"
fi

echo "== toolchain (after install) =="
missing=""
for tool in gcc g++ make autoconf automake bison flex gperf pkg-config git ccache; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '  %-12s %s\n' "$tool" "$("$tool" --version 2>&1 | head -1 | cut -c1-60)"
  else
    printf '  %-12s MISSING\n' "$tool"
    missing="$missing $tool"
  fi
done

echo "== headers =="
for header in freetype2 fontconfig cairo gtk+-3.0 libxml-2.0; do
  if pkg-config --exists "$header" 2>/dev/null; then
    printf '  %-14s present\n' "$header"
  else
    printf '  %-14s MISSING\n' "$header"
    missing="$missing pkg:$header"
  fi
done

if [ -n "$missing" ]; then
  echo "incomplete:$missing"
else
  echo "toolchain complete"
fi

echo "== build tree =="
mkdir -p "$BUILD"
echo "$BUILD"

cat <<'NEXT'

Next steps, deliberately not run:

  git clone https://git.libreoffice.org/core "$LO_SRC"     # decide upstream vs Collabora fork
  cd "$LO_SRC" && ./autogen.sh --enable-ccache ...
  time make -C writerfilter                                 # measure before committing to a full build

Then build-custom.sh applies a patch and rebuilds only what changed.
NEXT
