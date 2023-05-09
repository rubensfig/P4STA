# custom python modules
from analytics import analytics
from core import P4STA_utils
import rpyc

# globals
from management_ui import globals

from rest_framework.response import Response

from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer


# starts python receiver instance at external host

# @renderer_classes((TemplateHTMLRenderer, JSONRenderer))
@api_view(('GET',))
def start_external(request):

    cfg = P4STA_utils.read_current_cfg()

    ext_host_cfg = \
    globals.core_conn.root.get_current_extHost_obj().host_cfg
    print(ext_host_cfg)
        
    if "status_check" in ext_host_cfg and "needed_sudos_to_add" in ext_host_cfg["status_check"]:
        print("if true")
        sudos_ok = []
        indx_of_sudos_missing = []

        new_id = globals.core_conn.root.set_new_measurement_id()
        print("\nSET NEW MEASUREMENT ID")
        print(new_id)
        print("###############################\n")

        stamper_running, errors = globals.core_conn.root.start_external()
        # return render(
        #         request, "middlebox/output_external_started.html",
        #         {"running": stamper_running, "errors": list(errors),
        #          "cfg": cfg, "min_mtu": min(mtu_list)})
        return Response(new_id)

@api_view(('GET',))
def stop_external(request):
    # read time increases with amount of hosts
    stop_external = rpyc.timed(
        globals.core_conn.root.stop_external, 60*50)
    stoppable = stop_external()
    stoppable.wait()
    return Response("")
