db.subscribers.find({imsi: "001010000000001"}).forEach(function(sub) {
  sub.subscribed_rau_tau_timer = NumberInt(sub.subscribed_rau_tau_timer);
  sub.subscriber_status = NumberInt(sub.subscriber_status);
  sub.access_restriction_data = NumberInt(sub.access_restriction_data);
  sub.network_access_mode = NumberInt(sub.network_access_mode);
  sub.schema_version = NumberInt(sub.schema_version);
  
  if (sub.ambr) {
    sub.ambr.uplink.value = NumberInt(sub.ambr.uplink.value);
    sub.ambr.uplink.unit = NumberInt(sub.ambr.uplink.unit);
    sub.ambr.downlink.value = NumberInt(sub.ambr.downlink.value);
    sub.ambr.downlink.unit = NumberInt(sub.ambr.downlink.unit);
  }
  
  if (sub.slice) {
    sub.slice.forEach(function(sl) {
      sl.sst = NumberInt(sl.sst);
      if (sl.session) {
        sl.session.forEach(function(sess) {
          sess.type = NumberInt(sess.type);
          if (sess.qos) {
            sess.qos.index = NumberInt(sess.qos.index);
            sess.qos.arp.priority_level = NumberInt(sess.qos.arp.priority_level);
            sess.qos.arp.pre_emption_capability = NumberInt(sess.qos.arp.pre_emption_capability);
            sess.qos.arp.pre_emption_vulnerability = NumberInt(sess.qos.arp.pre_emption_vulnerability);
          }
          if (sess.ambr) {
            sess.ambr.uplink.value = NumberInt(sess.ambr.uplink.value);
            sess.ambr.uplink.unit = NumberInt(sess.ambr.uplink.unit);
            sess.ambr.downlink.value = NumberInt(sess.ambr.downlink.value);
            sess.ambr.downlink.unit = NumberInt(sess.ambr.downlink.unit);
          }
        });
      }
    });
  }
  db.subscribers.save(sub);
  print("Subscriber database types successfully repaired to NumberInt!");
});
