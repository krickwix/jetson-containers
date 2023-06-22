#!/usr/bin/env python
# coding: utf-8

import sys
import os
sys.path.append('../')
sys.path.append('../apps/')
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
import pyds, datetime

rtsp_url = os.getenv('RTSP_URL')
output_fps = os.getenv('FPS')
output_width = int(os.getenv('WIDTH'))
output_height = int(os.getenv('HEIGHT'))
rtsp_feed_name = os.getenv('RTSP_FEED_NAME')
jpeg_quality = int(os.getenv('JPEG_QUALITY'))

Gst.init(None)
pipeline = Gst.Pipeline()

def osd_sink_pad_buffer_probe(pad,info,u_data):
    return

def on_rtspsrc_pad_added(r,  pad):
    r.link(rtph264depay)
    rtph264depay.link(h264parser)
    h264parser.link(decoder)

# rtspsrc -> rtph264depay -> h264parser -> nvv4l2decoder -> nvstreammux -> nvvideoconvert -> nvjpegenc -> multifilesink
source = Gst.ElementFactory.make("rtspsrc","rtspsrc")
rtph264depay = Gst.ElementFactory.make("rtph264depay", "rtph264depay")
h264parser = Gst.ElementFactory.make("h264parse", "h264-parser")
decoder = Gst.ElementFactory.make("nvv4l2decoder", "nvv4l2-decoder")
streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
filewriter = Gst.ElementFactory.make("multifilesink","filesync")
jpegenc = Gst.ElementFactory.make("nvjpegenc","nvjpegenc")

source.set_property('location',rtsp_url)
source.set_property("latency", 0)
source.set_property("do-rtsp-keep-alive", 1)
source.connect("pad-added", on_rtspsrc_pad_added)

streammux.set_property('width', output_width)
streammux.set_property('height', output_height)
streammux.set_property('batch-size', 1)
streammux.set_property('live-source', True)
streammux.set_property('enable-padding', True)

decoder.set_property('enable-max-performance', True)
decoder.set_property('drop-frame-interval',16)
t = datetime.datetime.now()
timenow = t.strftime("%Y-%m-%d-%H-%M-%S")

location = "/captured/%s-%s_%%05d.jpg" % (timenow,rtsp_feed_name)
filewriter.set_property("location",location)

pipeline.add(source)
pipeline.add(h264parser)
pipeline.add(rtph264depay)
pipeline.add(decoder)
pipeline.add(streammux)
pipeline.add(nvvidconv)
pipeline.add(jpegenc)
pipeline.add(filewriter)

source.link(h264parser)
h264parser.link(decoder)

sinkpad = streammux.get_request_pad("sink_0")
srcpad = decoder.get_static_pad("src")
srcpad.link(sinkpad)

streammux.link(nvvidconv)

nvvidconv.link(jpegenc)
jpegenc.link(filewriter)

loop = GLib.MainLoop()
bus = pipeline.get_bus()
bus.add_signal_watch()
bus.connect ("message", bus_call, loop)

pipeline.set_state(Gst.State.PLAYING)
try:
    loop.run()
except:
    pass
pipeline.set_state(Gst.State.NULL)



