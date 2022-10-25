#include "selfdrive/modeld/models/nav.h"

#include <cstdio>
#include <cstring>

#include "common/mat.h"
#include "common/modeldata.h"
#include "common/params.h"
#include "common/timing.h"
#include "system/hardware/hw.h"


template<class T, size_t size>
constexpr const kj::ArrayPtr<const T> to_kj_array_ptr(const std::array<T, size> &arr) {
  return kj::ArrayPtr(arr.data(), arr.size());
}

void navmodel_init(NavModelState* s) {
  #ifdef USE_THNEED
    s->m = new ThneedModel("models/navmodel.thneed",
  #elif USE_ONNX_MODEL
    s->m = new ONNXModel("models/navmodel.onnx",
  #else
    s->m = new SNPEModel("models/navmodel.dlc",
  #endif
    &s->output[0], NAV_NET_OUTPUT_SIZE, USE_GPU_RUNTIME, false, false); // TODO: Use dsp runtime and set _use_tf8=true for quantized models (I think)
}

NavModelResult* navmodel_eval_frame(NavModelState* s, VisionBuf* buf) {
  // convert from uint8 to float32
  // memcpy(s->net_input_buf, buf->addr, INPUT_SIZE);
  for (int i=0; i<NAV_INPUT_SIZE; i++) {
    s->net_input_buf[i] = ((uint8_t*)buf->addr)[i];
  }

  double t1 = millis_since_boot();
  s->m->addImage(s->net_input_buf, NAV_INPUT_SIZE);
  s->m->execute();
  double t2 = millis_since_boot();

  NavModelResult *model_res = (NavModelResult*)&s->output;
  model_res->dsp_execution_time = (t2 - t1) / 1000.;
  return model_res;
}

void fill_plan(cereal::NavModelData::Builder &framed, const NavModelOutputPlan &plan) {
  std::array<float, TRAJECTORY_SIZE> pos_x, pos_y;
  std::array<float, TRAJECTORY_SIZE> pos_x_std, pos_y_std;

  for(int i=0; i<TRAJECTORY_SIZE; i++) {
    pos_x[i] = plan.mean[i].x;
    pos_y[i] = plan.mean[i].y;
    pos_x_std[i] = exp(plan.std[i].x);
    pos_y_std[i] = exp(plan.std[i].y);
  }

  auto position = framed.initPosition();
  position.setX(to_kj_array_ptr(pos_x));
  position.setY(to_kj_array_ptr(pos_y));
  position.setXStd(to_kj_array_ptr(pos_x_std));
  position.setYStd(to_kj_array_ptr(pos_y_std));
}

void navmodel_publish(PubMaster &pm, uint32_t frame_id, const NavModelResult &model_res, float execution_time) {
  // make msg
  MessageBuilder msg;
  auto framed = msg.initEvent().initNavModel();
  framed.setFrameId(frame_id);
  framed.setModelExecutionTime(execution_time);
  framed.setDspExecutionTime(model_res.dsp_execution_time);
  framed.setFeatures(to_kj_array_ptr(model_res.features.values));
  framed.setDesirePrediction(to_kj_array_ptr(model_res.desire_pred.values));
  fill_plan(framed, model_res.plans.get_best_prediction());

  pm.send("navModel", msg);
}

void navmodel_free(NavModelState* s) {
  delete s->m;
}