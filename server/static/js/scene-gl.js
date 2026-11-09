/* StrideBoard mini challenge scenes, redrawn in WebGL.
 *
 * Our own small renderer: no library. The athlete moves with the same rig as the SVG scenes
 * (workout_rig.py sends each exercise's joint positions in data-gl); here it is redrawn 60 times a
 * second with rounded, lit limbs, a glowing sky, soft clouds, layered hills, the walk course and
 * real particles (sparkles on each rep, dust, gems, confetti). The timer and labels stay as sharp
 * SVG text on top, and the walk still moves with app.js: this only follows it.
 *
 * The SVG scenes stay as the fallback: in Fast mode, with Reduce motion, without WebGL, or if
 * anything here fails. Lite phones get a lower resolution. Nothing runs while a scene is off screen.
 */
(function () {
  "use strict";
  var html = document.documentElement;
  var games = Array.prototype.slice.call(document.querySelectorAll(".game[data-gl]"));
  if (!games.length || html.classList.contains("fast")) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var LITE = html.classList.contains("lite");
  var MAX_SEG = 14, MAX_DOTS = 400, GROUND = 150;
  var CONFETTI = ["#F7DB6F", "#F49A8F", "#9EDCC6", "#A9CCF2", "#C9B8F2", "#FFFFFF"];

  // ------------------------------------------------------------------ shaders

  var VS_QUAD = "attribute vec2 a; void main() { gl_Position = vec4(a, 0.0, 1.0); }";

  var FS_SCENE = [
    "#ifdef GL_FRAGMENT_PRECISION_HIGH", "precision highp float;", "#else", "precision mediump float;", "#endif",
    "uniform vec2 u_res; uniform float u_t, u_px;",
    "uniform vec3 u_skyA, u_skyB, u_sun, u_far, u_near, u_grass, u_soil, u_scroll;",
    "uniform vec4 u_seg[" + MAX_SEG + "]; uniform vec4 u_col[" + MAX_SEG + "];",
    "uniform float u_n, u_headAt, u_front, u_ol, u_course, u_passed, u_hop;",
    "uniform vec3 u_head, u_main; uniform vec4 u_shadow, u_cxa, u_box; uniform vec2 u_cxb;",
    "const vec3 INK = vec3(0.090, 0.094, 0.110);",
    "const float TAU = 6.2831853;",
    // signed distance helpers; fill() turns a distance into smooth (anti-aliased) coverage
    "float fill(float d) { return 1.0 - smoothstep(-u_px, u_px, d); }",
    "float seg(vec2 p, vec2 a, vec2 b) { vec2 pa = p - a, ba = b - a;",
    "  float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-4), 0.0, 1.0); return length(pa - ba * h); }",
    "float tri(vec2 p, vec2 a, vec2 b, vec2 c) {",
    "  vec2 e0 = b - a, e1 = c - b, e2 = a - c, v0 = p - a, v1 = p - b, v2 = p - c;",
    "  vec2 q0 = v0 - e0 * clamp(dot(v0, e0) / dot(e0, e0), 0.0, 1.0);",
    "  vec2 q1 = v1 - e1 * clamp(dot(v1, e1) / dot(e1, e1), 0.0, 1.0);",
    "  vec2 q2 = v2 - e2 * clamp(dot(v2, e2) / dot(e2, e2), 0.0, 1.0);",
    "  float s = sign(e0.x * e2.y - e0.y * e2.x);",
    "  vec2 d = min(min(vec2(dot(q0, q0), s * (v0.x * e0.y - v0.y * e0.x)),",
    "                   vec2(dot(q1, q1), s * (v1.x * e1.y - v1.y * e1.x))),",
    "                   vec2(dot(q2, q2), s * (v2.x * e2.y - v2.y * e2.x)));",
    "  return -sqrt(d.x) * sign(d.y); }",
    // a lit, rounded surface: n is the surface normal, light from the upper left
    "vec3 lit(vec3 c, vec3 n) { vec3 L = normalize(vec3(-0.45, -0.75, 0.62));",
    "  float diff = max(dot(n, L), 0.0); float spec = pow(max(dot(n, normalize(L + vec3(0.0, 0.0, 1.0))), 0.0), 22.0);",
    "  return c * (0.6 + 0.5 * diff) + vec3(spec * 0.3) + c * 0.1 * pow(1.0 - n.z, 3.0); }",
    "float cloud(vec2 p) { float d = length(p) - 9.0; d = min(d, length(p - vec2(11.0, -5.0)) - 11.0);",
    "  d = min(d, length(p - vec2(24.0, 0.0)) - 9.0); vec2 b = abs(p - vec2(12.0, 4.0)) - vec2(8.0, 0.0);",
    "  return min(d, length(max(b, 0.0)) + min(max(b.x, b.y), 0.0) - 4.0); }",
    "float cx(int i) { if (i == 0) return u_cxa.x; if (i == 1) return u_cxa.y; if (i == 2) return u_cxa.z;",
    "  if (i == 3) return u_cxa.w; if (i == 4) return u_cxb.x; return u_cxb.y; }",
    "vec3 headPart(vec3 col, vec2 p) {",
    "  vec2 hc = u_head.xy; float R = u_head.z, s = R / 7.8; vec2 o = p - hc;",
    "  float band = 0.0; vec2 q = o / s;",
    "  if (u_front < 0.5) {",                                             // the headband's tail, behind the head
    "    float t = seg(q, vec2(-6.2, -1.6), vec2(-10.2, 0.3)) * s;",
    "    col = mix(col, INK, fill(t - 0.85 * s - 0.5 * s)); col = mix(col, vec3(0.898, 0.471, 0.420), fill(t - 0.85 * s)); }",
    "  float d = length(o);",
    "  col = mix(col, INK, fill(d - R - u_ol));",
    "  float inside = fill(d - R);",
    "  vec2 nn = o / R; vec3 n = vec3(nn, sqrt(max(0.0, 1.0 - dot(nn, nn))));",
    "  col = mix(col, lit(u_main, n), inside);",
    "  float yt = (u_front > 0.5 ? -3.4 : -3.2) - 1.5 * (1.0 - (q.x * q.x) / 49.0);",
    "  float bd = max(yt - q.y, q.y - yt - 2.6) * s;",
    "  col = mix(col, lit(vec3(0.898, 0.471, 0.420), n), fill(bd) * inside);",
    "  col = mix(col, INK, (fill(abs(bd) - 0.25 * s) * inside) * 0.55);",
    "  if (u_front > 0.5) {",
    "    for (int k = 0; k < 2; k++) { float sx = k == 0 ? -1.0 : 1.0;",
    "      col = mix(col, vec3(0.957, 0.604, 0.561), 0.5 * fill((length(q - vec2(4.4 * sx, 1.8)) - 1.4) * s));",
    "      col = mix(col, INK, fill((length(q - vec2(2.6 * sx, -0.6)) - 1.25) * s));",
    "      col = mix(col, vec3(1.0), fill((length(q - vec2(2.6 * sx + 0.45, -1.05)) - 0.42) * s)); }",
    "    float m = min(seg(q, vec2(-2.2, 2.6), vec2(0.0, 3.7)), seg(q, vec2(0.0, 3.7), vec2(2.2, 2.6)));",
    "    col = mix(col, INK, fill((m - 0.55) * s));",
    "  } else {",
    "    col = mix(col, vec3(0.957, 0.604, 0.561), 0.5 * fill((length(q - vec2(1.0, 2.0)) - 1.5) * s));",
    "    col = mix(col, INK, fill((length(q - vec2(3.4, -1.0)) - 1.25) * s));",
    "    col = mix(col, vec3(1.0), fill((length(q - vec2(3.85, -1.45)) - 0.42) * s));",
    "    float m = min(seg(q, vec2(3.2, 2.6), vec2(5.0, 3.4)), seg(q, vec2(5.0, 3.4), vec2(6.8, 2.2)));",
    "    col = mix(col, INK, fill((m - 0.55) * s)); }",
    "  return col; }",
    "void main() {",
    "  vec2 uv = gl_FragCoord.xy / u_res; vec2 p = vec2(uv.x * 320.0, (1.0 - uv.y) * 180.0);",
    // sky and sun
    "  vec3 col = mix(u_skyA, u_skyB, smoothstep(0.0, 150.0, p.y));",
    "  vec2 sp = p - vec2(196.0, 40.0); float sd = length(sp);",
    "  if (sd < 150.0) {",                                                 // the sun's glow and rays fade out by here
    "    float rays = (0.5 + 0.5 * sin(atan(sp.y, sp.x) * 12.0 + u_t * 0.25)) * exp(-sd / 70.0) * 0.1;",
    "    col += u_sun * (exp(-sd / 24.0) * 0.45 + rays); }",
    "  col = mix(col, u_sun, fill(sd - 13.0 - 0.6 * sin(u_t * 1.6)));",
    // clouds: soft white puffs drifting left, two copies so they wrap around seamlessly
    "  if (p.y < 74.0) for (int i = 0; i < 4; i++) {",                      // clouds only live up in the sky
    "    vec3 c = i == 0 ? vec3(22.0, 34.0, 1.0) : i == 1 ? vec3(128.0, 22.0, 0.8) : i == 2 ? vec3(226.0, 50.0, 1.1) : vec3(300.0, 30.0, 0.7);",
    "    float x = mod(c.x - u_scroll.x, 320.0);",
    "    for (int k = 0; k < 2; k++) { vec2 o = (p - vec2(x - float(k) * 320.0, c.y)) / c.z;",
    "      float d = cloud(o) * c.z;",
    "      col = mix(col, mix(col, vec3(0.0), 0.06), (1.0 - smoothstep(-2.0, 6.0, d - 2.0)) * 0.4 * step(0.0, o.y));",
    "      col = mix(col, mix(vec3(1.0), u_skyB, clamp((o.y + 8.0) / 30.0, 0.0, 0.35)), fill(d) * 0.94); } }",
    // far and near hills: smooth repeating ridges that scroll at different speeds (parallax)
    "  if (p.y > 76.0) {",                                                  // hills and ground: the lower part only
    "  float xf = p.x + u_scroll.y;",
    "  float hf = 100.0 - 12.0 * sin(xf * TAU * 2.0 / 320.0 + 0.6) - 7.0 * sin(xf * TAU * 5.0 / 320.0 + 2.1) - 3.0 * sin(xf * TAU * 11.0 / 320.0 + 0.4);",
    "  vec3 far = mix(u_far, u_skyB, 0.18) * (1.04 - 0.1 * clamp((p.y - hf) / 40.0, 0.0, 1.0));",
    "  far += 0.07 * (1.0 - smoothstep(0.0, 3.0, p.y - hf));",
    "  col = mix(col, far, smoothstep(hf - u_px, hf + u_px, p.y));",
    "  float xn = p.x + u_scroll.z;",
    "  float hn = 138.0 - 11.0 * pow(abs(sin(xn * 3.14159265 * 7.0 / 320.0)), 0.7) - 2.5 * sin(xn * TAU * 3.0 / 320.0);",
    "  vec3 near = u_near * (1.06 - 0.12 * clamp((p.y - hn) / 20.0, 0.0, 1.0)) + 0.07 * (1.0 - smoothstep(0.0, 2.5, p.y - hn));",
    "  col = mix(col, near, smoothstep(hn - u_px, hn + u_px, p.y));",
    // ground: grass with a scalloped edge over soil, pebbles and a few swaying flowers
    "  float dx = mod(p.x + 6.0, 12.0) - 6.0; float gb = 152.0 + sqrt(max(0.0, 36.0 - dx * dx));",
    "  float gt = 144.0 - 0.9 * abs(sin(p.x * 1.7)) * (0.6 + 0.4 * sin(p.x * 0.31));",
    "  vec3 soil = u_soil * (1.0 - 0.28 * clamp((p.y - 150.0) / 30.0, 0.0, 1.0));",
    "  col = mix(col, soil, smoothstep(149.0, 150.0, p.y));",
    "  if (p.y > 157.0) for (int i = 0; i < 8; i++) { vec3 pb = i == 0 ? vec3(18.0, 166.0, 3.0) : i == 1 ? vec3(64.0, 172.0, 2.0) : i == 2 ? vec3(104.0, 162.0, 2.5) : i == 3 ? vec3(150.0, 174.0, 3.0) :",
    "      i == 4 ? vec3(196.0, 165.0, 2.0) : i == 5 ? vec3(238.0, 171.0, 3.0) : i == 6 ? vec3(282.0, 163.0, 2.5) : vec3(312.0, 175.0, 2.0);",
    "    vec2 o = (p - pb.xy) / vec2(pb.z, pb.z * 0.6); col = mix(col, u_soil * 0.72, fill((length(o) - 1.0) * pb.z * 0.6) * 0.7); }",
    "  vec3 grass = u_grass * (1.14 - 0.24 * clamp((p.y - gt) / 12.0, 0.0, 1.0));",
    "  col = mix(col, grass, smoothstep(gt - u_px, gt + u_px, p.y) * (1.0 - smoothstep(gb - u_px, gb + u_px, p.y)));",
    "  col += 0.1 * (1.0 - smoothstep(0.0, 1.6, abs(p.y - gt - 0.6))) * step(p.y, gb);",
    "  if (p.y > 133.0 && p.y < 147.5) for (int i = 0; i < 4; i++) { vec2 f = i == 0 ? vec2(40.0, 1.0) : i == 1 ? vec2(120.0, 0.0) : i == 2 ? vec2(262.0, 1.0) : vec2(300.0, 0.0);",
    "    float sw = 0.7 * sin(u_t * 1.4 + f.x); vec2 top = vec2(f.x + sw, 138.0);",
    "    col = mix(col, vec3(0.184, 0.541, 0.278), fill(seg(p, vec2(f.x, 146.0), top) - 0.7));",
    "    vec3 petal = f.y > 0.5 ? vec3(1.0) : vec3(0.969, 0.761, 0.855);",
    "    col = mix(col, petal, fill(length(p - top) - 2.6)); col = mix(col, vec3(1.0, 0.89, 0.43), fill(length(p - top) - 1.0)); }",
    // the walk course: dashed trail, start line, four checkpoint posts and the finish flag
    "  }",
    "  if (u_course > 0.5 && p.y > 101.0 && p.y < 159.0) {",
    "    float c0 = cx(0), c5 = cx(5);",
    "    float dash = 1.0 - smoothstep(1.9, 2.3, mod(p.x - c0, 7.0));",
    "    col = mix(col, vec3(1.0), 0.55 * dash * fill(abs(p.y - 157.0) - 1.0) * step(c0, p.x) * step(p.x, c5));",
    "    vec2 sb = abs(p - vec2(c0, 149.0)) - vec2(1.5, 5.0); col = mix(col, vec3(1.0), 0.9 * fill(max(sb.x, sb.y)));",
    "    for (int i = 1; i < 5; i++) { float x = cx(i);",
    "      float hop = abs(float(i) - u_passed) < 0.5 ? -4.0 * sin(3.14159 * clamp(u_hop / 0.45, 0.0, 1.0)) : 0.0;",
    "      float pole = seg(p, vec2(x, 150.0), vec2(x, 129.0 + hop));",
    "      col = mix(col, INK, fill(pole - 1.6)); col = mix(col, vec3(0.357, 0.275, 0.212), fill(pole - 1.0));",
    "      vec3 pc = float(i) <= u_passed + 0.5 ? vec3(0.435, 0.827, 0.604) : vec3(0.969, 0.859, 0.435);",
    "      float t = tri(p, vec2(x, 129.0 + hop), vec2(x + 12.0, 133.0 + hop), vec2(x, 137.0 + hop));",
    "      col = mix(col, INK, fill(t - 0.6)); col = mix(col, pc * (1.08 - 0.2 * clamp((p.x - x) / 12.0, 0.0, 1.0)), fill(t)); }",
    "    float fp = seg(p, vec2(c5, 150.0), vec2(c5, 104.0));",
    "    col = mix(col, INK, fill(fp - 1.8)); col = mix(col, vec3(0.357, 0.275, 0.212), fill(fp - 1.2));",
    "    float lx = p.x - c5 - 1.0; float ly = p.y - 106.0 - sin(lx * 0.35 - u_t * 5.0) * 1.3 * clamp(lx / 18.0, 0.0, 1.0);",
    "    vec2 fb = abs(vec2(lx, ly) - vec2(9.0, 6.75)) - vec2(9.0, 6.75); float fd = max(fb.x, fb.y);",
    "    float chk = mod(floor(lx / 4.5) + floor(ly / 4.5), 2.0);",
    "    vec3 fc = mix(vec3(1.0), vec3(0.114, 0.129, 0.251), chk) * (0.92 + 0.12 * sin(lx * 0.35 - u_t * 5.0));",
    "    col = mix(col, INK, fill(fd - 0.6)); col = mix(col, fc, fill(fd)); }",
    // the athlete's soft shadow, then the body: each limb a lit rounded capsule with an ink outline
    "  vec2 so = (p - u_shadow.xy) / u_shadow.zw;",
    "  if (abs(so.y) < 1.0) col = mix(col, vec3(0.0), 0.2 * (1.0 - smoothstep(0.35, 1.0, length(so))));",
    "  if (p.x > u_box.x && p.x < u_box.z && p.y > u_box.y && p.y < u_box.w)",   // the athlete only inside their box
    "  for (int i = 0; i < " + MAX_SEG + "; i++) {",
    "    if (float(i) >= u_n) break;",
    "    vec4 s = u_seg[i]; vec4 c = u_col[i];",
    "    vec2 pa = p - s.xy, ba = s.zw - s.xy;",
    "    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-4), 0.0, 1.0);",
    "    vec2 dv = pa - ba * h; float d = length(dv);",
    "    col = mix(col, INK, fill(d - c.w - u_ol));",
    "    vec2 nn = dv / max(c.w, 1e-3); vec3 n = vec3(nn, sqrt(max(0.0, 1.0 - dot(nn, nn))));",
    "    col = mix(col, lit(c.rgb, n), fill(d - c.w));",
    "    if (abs(float(i) - u_headAt) < 0.5 && length(p - u_head.xy) < u_head.z * 1.65) col = headPart(col, p);",
    "  }",
    "  vec2 vg = uv - 0.5; col *= 1.0 - 0.18 * dot(vg, vg);",
    "  gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);",
    "}"
  ].join("\n");

  var VS_DOTS = [
    "attribute vec2 a_pos; attribute vec4 a_col; attribute vec3 a_misc; uniform float u_ppu;",
    "varying vec4 v_col; varying vec2 v_misc;",
    "void main() { gl_Position = vec4(a_pos.x / 160.0 - 1.0, 1.0 - a_pos.y / 90.0, 0.0, 1.0);",
    "  gl_PointSize = max(1.0, a_misc.x * u_ppu); v_col = a_col; v_misc = a_misc.yz; }"
  ].join("\n");

  var FS_DOTS = [
    "precision mediump float; varying vec4 v_col; varying vec2 v_misc;",
    "void main() {",
    "  vec2 q = gl_PointCoord * 2.0 - 1.0; float c = cos(v_misc.x), s = sin(v_misc.x);",
    "  q = vec2(c * q.x - s * q.y, s * q.x + c * q.y);",
    "  float shape = v_misc.y, a = 0.0; vec3 rgb = v_col.rgb;",
    "  if (shape < 0.5) {",                                                   // gem
    "    float d = abs(q.x) / 0.78 + abs(q.y); a = 1.0 - smoothstep(0.86, 0.94, d);",
    "    rgb = mix(rgb, vec3(0.165, 0.549, 0.706), smoothstep(0.66, 0.76, d));",
    "    rgb = mix(rgb, rgb * 0.82, step(0.0, q.x) * step(0.0, q.y));",
    "    rgb += 0.6 * (1.0 - smoothstep(0.0, 0.3, length(q - vec2(-0.18, -0.32))));",
    "  } else if (shape < 1.5) {",                                            // confetti
    "    vec2 b = abs(q) - vec2(0.45, 0.85); a = 1.0 - smoothstep(-0.08, 0.0, max(b.x, b.y)); rgb *= 0.86 + 0.22 * q.y;",
    "  } else if (shape < 2.5) {",                                            // soft puff
    "    a = (1.0 - smoothstep(0.15, 1.0, length(q))) * 0.9;",
    "  } else if (shape < 3.5) {",                                            // sparkle
    "    float d = length(q); float star = max(0.0, 1.0 - abs(q.x * q.y) * 16.0 - d);",
    "    a = clamp(star * 1.7 + (1.0 - smoothstep(0.0, 0.55, d)) * 0.55, 0.0, 1.0);",
    "    rgb = mix(rgb, vec3(1.0), 0.6 * (1.0 - smoothstep(0.0, 0.3, d)));",
    "  } else {",                                                             // sweat drop
    "    float d = length(vec2(q.x * (1.0 + 0.95 * max(0.0, -q.y)), q.y - 0.25)) - 0.6;",
    "    a = 1.0 - smoothstep(-0.08, 0.0, d); rgb += 0.5 * (1.0 - smoothstep(0.0, 0.2, length(q - vec2(-0.18, 0.15))));",
    "  }",
    "  a *= v_col.a; gl_FragColor = vec4(rgb * a, a);",
    "}"
  ].join("\n");

  // ------------------------------------------------------------------ small helpers

  function hex(s) {
    s = (s || "").trim();
    var m = /^#([0-9a-f]{6})$/i.exec(s);
    if (m) {
      var v = parseInt(m[1], 16);
      return [(v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255];
    }
    m = /rgba?\(([^)]+)\)/.exec(s);
    if (m) {
      var p = m[1].split(",").map(parseFloat);
      return [p[0] / 255, p[1] / 255, p[2] / 255];
    }
    return [1, 1, 1];
  }

  function compile(gl, type, src) {
    var sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      if (window.console) console.warn("scene-gl:", gl.getShaderInfoLog(sh));
      return null;
    }
    return sh;
  }

  function program(gl, vs, fs) {
    var v = compile(gl, gl.VERTEX_SHADER, vs), f = compile(gl, gl.FRAGMENT_SHADER, fs);
    if (!v || !f) return null;
    var p = gl.createProgram();
    gl.attachShader(p, v);
    gl.attachShader(p, f);
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return null;
    var u = {}, n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    for (var i = 0; i < n; i++) {
      var name = gl.getActiveUniform(p, i).name.replace(/\[0\]$/, "");
      u[name] = gl.getUniformLocation(p, name);
    }
    return {p: p, u: u};
  }

  function rand(a, b) { return a + Math.random() * (b - a); }

  // A pose's colours, parsed once
  function prepare(pose) {
    pose.rgb = pose.segs.map(function (s) { return hex(s[2]); });
    pose.main = pose.rgb[pose.head_after];
    pose.ankles = [];
    pose.segs.forEach(function (s, i) { if (/^(far)?leg2$|^leg[lr]2$/.test(s[0])) pose.ankles.push(i); });
    return pose;
  }

  // The rig's 24 frames, blended smoothly for any moment in the cycle
  function sample(pose, phase, out) {
    var n = pose.frames.length, f = phase * n, i = Math.floor(f) % n, j = (i + 1) % n, k = f - Math.floor(f);
    var A = pose.frames[i], B = pose.frames[j];
    for (var m = 0; m < A.length; m++) out[m] = A[m] + (B[m] - A[m]) * k;
    return out;
  }

  // ------------------------------------------------------------------ one scene

  function start(game) {
    var info = JSON.parse(game.getAttribute("data-gl"));
    var canvas = document.createElement("canvas");
    canvas.className = "gl";
    canvas.setAttribute("aria-hidden", "true");
    var gl = canvas.getContext("webgl", {alpha: false, antialias: false, depth: false, stencil: false,
                                          powerPreference: "low-power"});
    if (!gl) return;
    var scene = program(gl, VS_QUAD, FS_SCENE), dots = program(gl, VS_DOTS, FS_DOTS);
    if (!scene || !dots) return;

    Object.keys(info.poses).forEach(function (k) { prepare(info.poses[k]); });
    var kind = info.kind, size = info.size, s = size / 100;
    var mainPose = info.poses[Object.keys(info.poses)[0]];
    var walker = game.querySelector(".walker");
    var stage = game.closest(".win-stage1, .win-walk .win-stage2");   // cross-fading parts of a walk's win
    var course = info.course || [0, 0, 0, 0, 0, 0];

    var quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    var dotBuf = gl.createBuffer();
    var dotData = new Float32Array(MAX_DOTS * 9);
    var aQuad = gl.getAttribLocation(scene.p, "a");
    var aPos = gl.getAttribLocation(dots.p, "a_pos"), aCol = gl.getAttribLocation(dots.p, "a_col"),
        aMisc = gl.getAttribLocation(dots.p, "a_misc");

    game.insertBefore(canvas, game.firstChild);
    game.classList.add("gl-on");

    var seg = new Float32Array(MAX_SEG * 4), col = new Float32Array(MAX_SEG * 4), tmp = [];
    var colours = {}, frame = 0, tick = 0, quality = 1, slow = 0, last = 0, visible = true, alive = true, faded = false;
    var burstsDone = 0, odd = 0;
    var t0 = performance.now() + (game.closest(".win-walk .win-stage2") ? 3200 : 0);
    var particles = [], lastPhase = 0, lastLift = 0, grounded = {}, passed = -1, passedAt = -9, finished = false;
    var headPos = [0, 0], torsoMid = [160, 100];

    function readColours() {
      var cs = getComputedStyle(game);
      ["sky-a", "sky-b", "sun", "far", "near", "grass", "soil"].forEach(function (k) {
        colours[k] = hex(cs.getPropertyValue("--g-" + k));
      });
    }
    readColours();

    function resize() {
      var w = canvas.clientWidth || game.clientWidth || 320;
      var dpr = Math.min(window.devicePixelRatio || 1, LITE ? 1.25 : 2);
      var px = Math.max(160, Math.round(Math.min(w * dpr * quality, LITE ? 560 : 960)));
      var py = Math.round(px * 9 / 16);
      if (canvas.width !== px || canvas.height !== py) { canvas.width = px; canvas.height = py; }
    }

    // ---- particles: [x, y, vx, vy, gravity, life, max, size, rot, spin, r, g, b, a, shape, grow, drag]
    function add(x, y, vx, vy, g, life, size, rgb, a, shape, spin, grow, drag) {
      if (particles.length >= MAX_DOTS - 8) return;
      particles.push({x: x, y: y, vx: vx, vy: vy, g: g, life: life, max: life, size: size, rot: rand(0, 6.28),
                      spin: spin || 0, c: rgb, a: a, shape: shape, grow: grow || 0, drag: drag || 0});
    }
    function sparkles(x, y, n, rgb, speed) {
      for (var i = 0; i < n; i++) {
        var ang = rand(0, 6.28), v = rand(.4, 1) * (speed || 40);
        add(x, y, Math.cos(ang) * v, Math.sin(ang) * v, 20, rand(.45, .8), rand(3.5, 6), rgb || [1, .89, .43], 1, 3, 0, -2, 3);
      }
    }
    function puff(x, y, n) {
      for (var i = 0; i < n; i++) {
        add(x + rand(-2, 2), y - rand(0, 1.5), rand(-14, 14), rand(-9, -3), 0, rand(.45, .7), rand(3, 5),
            [.85, .72, .58], .55, 2, 0, 9, 2);
      }
    }
    function confetti(x, y, n, spread, up) {
      for (var i = 0; i < n; i++) {
        var ang = rand(-spread, spread), v = rand(.65, 1) * up;
        add(x, y, Math.sin(ang) * v, -Math.cos(ang) * v, 150, rand(1.3, 1.9), rand(4.5, 6.5),
            hex(CONFETTI[i % CONFETTI.length]), 1, 1, rand(-9, 9), 0, .6);
      }
    }
    function gemPop(x, y) { add(x, y, rand(-8, 8), -46, 30, 1.1, 13, [.435, .827, .941], 1, 0, rand(-2, 2), 0, 1.2); }

    // ---- what each kind of scene does, every frame
    var walkerX = null;
    function athletePlacement(t) {
      if (kind === "walk" || kind === "finish") {
        var walking = kind === "finish" || walker.classList.contains("walking");
        if (walking || walkerX === null || frame % 15 === 0) {        // reading styles costs: only when it moves
          var m = /matrix\(([^)]+)\)/.exec(getComputedStyle(walker).transform || "");
          walkerX = m ? parseFloat(m[1].split(",")[4]) : course[0];
        }
        var x = walkerX;
        return {x: x - size / 2, pose: walking ? info.poses.walk : info.poses.stand, walking: walking, wx: x};
      }
      return {x: 160 - size / 2, pose: mainPose};
    }

    function events(t, dt, place, v, n, phase, now) {
      var oy = GROUND - .97 * size, lift = v[n * 4 + 2];
      // ambient: three floating gems, light motes drifting up
      if (kind !== "cheer") {
        [[92, 78, 0], [246, 92, .9], [276, 70, 1.7]].forEach(function (g) { draw(g[0], g[1] - 3 - 3 * Math.sin((t + g[2]) * 2.4), 15, 0, [.435, .827, .941], 1, 0); });
        if (Math.random() < dt * 1.2) gemTwinkle();
      }
      if (Math.random() < dt * 2.5) add(rand(0, 320), rand(60, 140), rand(-3, 3), rand(-7, -3), 0, rand(2, 3.5), rand(2, 3.4), [1, 1, 1], .35, 3, 0, 0, 0);

      var wrapped = phase < lastPhase;
      if (kind === "work") {
        var ex = Object.keys(info.poses)[0];
        if (wrapped && ex !== "plank") { sparkles(torsoMid[0], torsoMid[1], 12, null, 46); gemPop(torsoMid[0] + 6, torsoMid[1] - 8); }
        if (ex === "plank" && (wrapped || (phase >= .5 && lastPhase < .5))) {
          add(headPos[0] + 3, headPos[1] - 6, rand(4, 8), -10, 120, 1.0, 5, [.486, .784, .949], .95, 4, 0, 0, 0);
          if (wrapped) sparkles(torsoMid[0], torsoMid[1] - 4, 6, null, 26);
        }
        if (ex === "jacks" && lastLift > 1.2 && lift <= .4) {
          mainPose.ankles.forEach(function (i) { puff(place.x + v[i * 4 + 2] * s, GROUND, 3); });
        }
      }
      if (kind === "walk" || kind === "finish") {
        if (place.walking) {
          place.pose.ankles.forEach(function (i) {
            var y = oy + v[i * 4 + 3] * s, down = y >= GROUND - 2.4 * s;
            if (down && grounded[i] === false) puff(place.x + v[i * 4 + 2] * s, GROUND, 2);
            grounded[i] = down;
          });
        }
        var p = kind === "finish" ? 4 : (frame % 10 === 0 || passed < 0 ? game.querySelectorAll(".g-cp.passed").length : passed);
        if (passed >= 0 && p > passed) {
          passedAt = t;
          var px = course[Math.min(p, 4)];
          sparkles(px + 6, 133, 16, [.435, .827, .604], 52); gemPop(px + 6, 128);
        }
        passed = p;
        if (kind === "finish" && !finished && place.wx > course[5] + 4) {
          finished = true;
          confetti(course[5] + 10, 108, 34, 1.2, 120);
          sparkles(course[5] + 10, 112, 18, null, 60);
        }
      }
      if (kind === "cheer") {
        if (now >= t0 && burstsDone === 0) { burstsDone = 1; burst(); }
        if (t > 1.3 && burstsDone === 1) { burstsDone = 2; burst(); }
        if (phase >= .3 && lastPhase < .3) confetti(160, 112, 18, 1.35, 130);
        if (Math.random() < dt * 16) add(rand(0, 320), -8, rand(-12, 12), rand(30, 60), 6, 4, rand(4.5, 6.5),
                                          hex(CONFETTI[Math.floor(rand(0, 6))]), 1, 1, rand(-6, 6), 0, 0);
      }
      lastPhase = phase; lastLift = lift;
    }
    function burst() {
      for (var i = 0; i < 8; i++) {
        var ang = i / 8 * 6.283;
        add(160, 96, Math.cos(ang) * 150, Math.sin(ang) * 150, 0, 1.0, 13, [.435, .827, .941], 1, 0, 0, 0, 2.6);
      }
      sparkles(160, 96, 20, null, 80);
    }
    function gemTwinkle() {
      var g = [[92, 78], [246, 92], [276, 70]][Math.floor(rand(0, 3))];
      add(g[0] + rand(-5, 5), g[1] + rand(-8, 2), 0, -4, 0, .6, rand(5, 7), [1, 1, 1], .9, 3, 0, -3, 0);
    }

    var drawList = [];
    function draw(x, y, size, rot, rgb, a, shape) { drawList.push(x, y, rgb[0], rgb[1], rgb[2], a, size, rot, shape); }

    // ---- the frame
    function render(now) {
      if (!alive) return;
      requestAnimationFrame(render);
      if (!document.body.contains(game)) { stop(); return; }
      if (!visible || document.hidden) { last = 0; return; }
      if (stage && (tick++ % 20 === 0)) faded = parseFloat(getComputedStyle(stage).opacity) < .02;
      if (faded) return;          // not showing: the finish line after its fade, or the celebration before it
      if (LITE && (++odd & 1)) return;           // Lite phones: 30 frames a second, half the battery
      var dt = last ? Math.min(.07, (now - last) / 1000) : 1 / 60;
      // A slow phone draws at a lower resolution instead of stuttering
      if (last && now - last > (LITE ? 50 : 26)) { if (++slow > 45 && quality > .55) { quality *= .8; slow = 0; } } else slow = Math.max(0, slow - 1);
      last = now;
      frame++;
      if (frame % 90 === 0) readColours();
      resize();
      var t = Math.max(0, (now - t0) / 1000);

      // the athlete
      var place = athletePlacement(t), pose = place.pose;
      var phase = (t / pose.dur) % 1, v = sample(pose, phase, tmp), n = pose.segs.length;
      var oy = GROUND - .97 * size;
      for (var i = 0; i < n; i++) {
        seg[i * 4] = place.x + v[i * 4] * s; seg[i * 4 + 1] = oy + v[i * 4 + 1] * s;
        seg[i * 4 + 2] = place.x + v[i * 4 + 2] * s; seg[i * 4 + 3] = oy + v[i * 4 + 3] * s;
        var c = pose.rgb[i];
        col[i * 4] = c[0]; col[i * 4 + 1] = c[1]; col[i * 4 + 2] = c[2]; col[i * 4 + 3] = pose.segs[i][1] / 2 * s;
      }
      var hx = place.x + v[n * 4] * s, hy = oy + v[n * 4 + 1] * s, lift = v[n * 4 + 2];
      // A box around the athlete (limbs, outline, head, headband tail): the shader skips them elsewhere
      var bx0 = hx - 12.5 * s, by0 = hy - 9.5 * s, bx1 = hx + 9.5 * s, by1 = hy + 9.5 * s, pad = 9 * s;
      for (i = 0; i < n * 4; i += 2) {
        bx0 = Math.min(bx0, seg[i] - pad); bx1 = Math.max(bx1, seg[i] + pad);
        by0 = Math.min(by0, seg[i + 1] - pad); by1 = Math.max(by1, seg[i + 1] + pad);
      }
      headPos = [hx, hy];
      var ti = pose.head_after;
      torsoMid = [(seg[ti * 4] + seg[ti * 4 + 2]) / 2, (seg[ti * 4 + 1] + seg[ti * 4 + 3]) / 2];

      drawList.length = 0;
      events(t, dt, place, v, n, phase, now);
      step(dt);

      // draw the world and the athlete
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.disable(gl.BLEND);
      gl.useProgram(scene.p);
      var U = scene.u;
      gl.uniform2f(U.u_res, canvas.width, canvas.height);
      gl.uniform1f(U.u_t, t % 600);
      gl.uniform1f(U.u_px, 320 / canvas.width);
      gl.uniform3fv(U.u_skyA, colours["sky-a"]); gl.uniform3fv(U.u_skyB, colours["sky-b"]);
      gl.uniform3fv(U.u_sun, colours.sun); gl.uniform3fv(U.u_far, colours.far); gl.uniform3fv(U.u_near, colours.near);
      gl.uniform3fv(U.u_grass, colours.grass); gl.uniform3fv(U.u_soil, colours.soil);
      gl.uniform3f(U.u_scroll, (t * 320 / 70) % 320, (t * 320 / 50) % 320, (t * 320 / 24) % 320);
      gl.uniform4fv(U.u_seg, seg); gl.uniform4fv(U.u_col, col);
      gl.uniform1f(U.u_n, n); gl.uniform1f(U.u_headAt, ti); gl.uniform1f(U.u_front, pose.view === "front" ? 1 : 0);
      gl.uniform1f(U.u_ol, 1.3 * s);
      gl.uniform3f(U.u_head, hx, hy, 7.8 * s); gl.uniform3fv(U.u_main, pose.main);
      gl.uniform4f(U.u_box, bx0, by0, bx1, by1);
      var shrink = 1 - Math.min(.4, lift / 20);
      gl.uniform4f(U.u_shadow, place.x + 50 * s, GROUND + .5, (pose.view === "front" ? 18 : 30) * s * shrink, 2.8 * s * shrink);
      gl.uniform1f(U.u_course, info.course ? 1 : 0);
      gl.uniform4f(U.u_cxa, course[0], course[1], course[2], course[3]); gl.uniform2f(U.u_cxb, course[4], course[5]);
      gl.uniform1f(U.u_passed, Math.max(0, passed)); gl.uniform1f(U.u_hop, t - passedAt);
      gl.bindBuffer(gl.ARRAY_BUFFER, quad);
      gl.enableVertexAttribArray(aQuad);
      gl.vertexAttribPointer(aQuad, 2, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.disableVertexAttribArray(aQuad);

      // particles on top
      var count = 0, k;
      for (k = 0; k + 8 < drawList.length && count < MAX_DOTS; k += 9, count++) {
        for (var m = 0; m < 9; m++) dotData[count * 9 + m] = drawList[k + m];
      }
      for (k = 0; k < particles.length && count < MAX_DOTS; k++) {
        var p = particles[k], f = p.life / p.max, fade = Math.min(1, f * 3);
        var o = count * 9;
        dotData[o] = p.x; dotData[o + 1] = p.y; dotData[o + 2] = p.c[0]; dotData[o + 3] = p.c[1]; dotData[o + 4] = p.c[2];
        dotData[o + 5] = p.a * fade; dotData[o + 6] = Math.max(.5, p.size + p.grow * (1 - f)); dotData[o + 7] = p.rot;
        dotData[o + 8] = p.shape;
        count++;
      }
      if (count) {
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
        gl.useProgram(dots.p);
        gl.uniform1f(dots.u.u_ppu, canvas.width / 320);
        gl.bindBuffer(gl.ARRAY_BUFFER, dotBuf);
        gl.bufferData(gl.ARRAY_BUFFER, dotData.subarray(0, count * 9), gl.DYNAMIC_DRAW);
        gl.enableVertexAttribArray(aPos); gl.enableVertexAttribArray(aCol); gl.enableVertexAttribArray(aMisc);
        gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 36, 0);
        gl.vertexAttribPointer(aCol, 4, gl.FLOAT, false, 36, 8);
        gl.vertexAttribPointer(aMisc, 3, gl.FLOAT, false, 36, 24);
        gl.drawArrays(gl.POINTS, 0, count);
        gl.disableVertexAttribArray(aPos); gl.disableVertexAttribArray(aCol); gl.disableVertexAttribArray(aMisc);
      }
    }

    function step(dt) {
      for (var i = particles.length - 1; i >= 0; i--) {
        var p = particles[i];
        p.life -= dt;
        if (p.life <= 0 || p.y > 200) { particles.splice(i, 1); continue; }
        var d = Math.max(0, 1 - p.drag * dt);
        p.vx *= d; p.vy = p.vy * d + p.g * dt;
        p.x += p.vx * dt; p.y += p.vy * dt; p.rot += p.spin * dt;
        if (p.shape === 1) p.x += Math.sin(p.life * 5 + p.rot) * .25;     // confetti flutters
      }
    }

    function stop() {
      alive = false;
      var lose = gl.getExtension("WEBGL_lose_context");
      if (lose) lose.loseContext();
    }

    canvas.addEventListener("webglcontextlost", function (e) {
      e.preventDefault();
      alive = false;
      game.classList.remove("gl-on");            // the SVG scene takes over
      if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
    });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) { visible = entries[entries.length - 1].isIntersecting; }).observe(game);
    }
    requestAnimationFrame(render);
  }

  games.forEach(function (g) {
    try { start(g); } catch (e) {
      g.classList.remove("gl-on");
      var c = g.querySelector("canvas.gl");
      if (c) c.parentNode.removeChild(c);
      if (window.console) console.warn("scene-gl:", e);
    }
  });
})();
