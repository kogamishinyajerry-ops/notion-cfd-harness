FROM openfoam/openfoam10-paraview510

# Copy the entrypoint wrapper script that imports adv_protocols.py before
# starting the ParaView Web launcher. The wrapper is installed as the
# container's ENTRYPOINT so it runs as PID 1 inside every session container.
COPY entrypoint_wrapper.sh /entrypoint_wrapper.sh
RUN chmod +x /entrypoint_wrapper.sh

# Use exec form so the wrapper receives PID 1 and can in turn exec pvpython.
# CMD arguments (passed at runtime) become the wrapper's $@.
ENTRYPOINT ["/entrypoint_wrapper.sh"]
