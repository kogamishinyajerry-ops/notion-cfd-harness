FROM openfoam/openfoam10-paraview510

# Install trame stack — replaces vtk.web.launcher + wslink server stack
# These versions are compatible with Python 3.9.18 in openfoam10-paraview510
# trame 3.12.0 transitively brings wslink >= 2.3.3 (do NOT install wslink separately)
RUN pip install --no-cache-dir \
    trame==3.12.0 \
    trame-vtk==2.11.6 \
    trame-vuetify==3.2.1

# Copy trame server entrypoint script (replaces entrypoint_wrapper.sh + launcher.py + adv_protocols.py)
COPY trame_server.py /trame_server.py

# Direct start — no entrypoint wrapper needed.
# The container CMD becomes: pvpython /trame_server.py --port N
CMD ["pvpython", "/trame_server.py"]
