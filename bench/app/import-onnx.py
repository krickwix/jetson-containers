import onnx.hub as hub
import onnxruntime as rt
import numpy as np
import pandas as pd
import os, time, statistics, boto3

def iterate_on_model( models, df ):
    # Iterating through the model list
    for model in models:
        try:
            m = hub.load(model.model,force_reload=True) # Load the model from the hub
        except Exception as e:
            print(e)
            continue
        # Full path to the expected model file
        f = os.path.dirname(hub.get_dir() + "/" + model.model_path) + "/" + model.model_sha + "_" + os.path.basename(model.model_path)
        # Create an onnx session
        try:
            session = rt.InferenceSession(f, providers=['CUDAExecutionProvider'],sess_options=opts)
            # session = rt.InferenceSession(f, providers=rt.get_available_providers(),sess_options=opts)
        except Exception as e:  # The onnx model file might not map to the model version
            print(e)
            continue
        # Guessing the inut shape expected by the model
        s = session.get_inputs()[0].shape
        t = session.get_inputs()[0].type
        print("The model expects input shape: ", s, " ", t)
        # Creating an input tensor
        if t == "tensor(float)":
            if s[0] == "batch_size" or s[0] == "N" or s[0] == "unk__576" or s[0] == "unk__2104":
                s[0] = 1
            try:
                ximg = np.random.rand(s[0], s[1], s[2], s[3]).astype(np.float32)
            except:
                continue
        input_name = session.get_inputs()[0].name

        times = []
        for i in range(nb_iters):
            start = time.time()
            result = session.run(None, {input_name: ximg})
            end = time.time()
            times.append(end-start)
        inference_timing_alltimes = times
        d = {model.model:inference_timing_alltimes}
        all_df = pd.DataFrame(d)
        if os.path.exists(f):
            os.remove(f)

        return all_df

nb_iters = 1000
publish_results = True

# S3 bucket for pushing results
s3_bucket = "cisco-eti-gbear-scratch"

# Device identity string
try:
    device_model = open('/device-tree/model','r').readline().replace("\x00","").replace(" ","")
    device_serial = open('/device-tree/serial-number','r').readline().replace("\x00","")
    device_id = device_model + "-" + device_serial
except:
    print("This device is unknown")
    device_id = "unk"
timestring = time.strftime("%m%d%Y%H%M%S", time.localtime())
resultFile = "results_" + device_id + "_" + timestring + ".csv"

# Tuning the onnxruntime
opts = rt.SessionOptions()
#opts.intra_op_num_threads = 1
opts.graph_optimization_level = rt.GraphOptimizationLevel.ORT_DISABLE_ALL
rt.set_default_logger_severity(3)

# Dataframe to hold bench results
df = pd.DataFrame()
alldf = pd.DataFrame()
modelList = open("models.txt").read().split("\n")
for ml in modelList:
    # Retrieving models list from the hub
    all_models = hub.list_models(tags=['vision'],model=ml)
    df = iterate_on_model(all_models,df)
    alldf = pd.concat([alldf,df],axis=1)
    if os.path.exists(resultFile):
        os.remove(resultFile)
    # Building the csv results file
    alldf.to_csv(resultFile)
    # publishing to the S3 bucket
    if publish_results == True:
        s3 = boto3.resource('s3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        s3.Bucket(s3_bucket).upload_file(resultFile, "bench/"+resultFile)
