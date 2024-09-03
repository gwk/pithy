
set -ex

cd $HOME/src/python
mkdir -p _build
cd _build

export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig
export CFLAGS='-I/usr/local/include'
export LDFLAGS='-L/usr/local/lib -Wl,-rpath /usr/local/lib'

 ../configure \
 --enable-optimizations \
--enable-loadable-sqlite-extensions \
--with-pkg-config=yes


make -j$(nproc)
sudo make -j$(nproc) install

(cd /usr/local/bin && sudo ln -sf python3.12 python)
(cd /usr/local/bin && sudo ln -sf pip3.12 pip)
hash -r # Make sure the new python is available.
sudo pip install -U pip


python_src="https://www.python.org/ftp/python/3.12.5/Python-3.12.5.tar.xz"
