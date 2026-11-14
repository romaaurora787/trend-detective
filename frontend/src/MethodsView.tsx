import { useEffect, useState } from "react";
import { api, examples, type Validation } from "./api";
import { Panel, Reveal } from "./Chart";

const pct = (xs: number[]) => xs.map((x) => x * 100);

export function MethodsView() {
  const [v, setV] = useState<Validation>(examples.validation);
  useEffect(() => { api.validation().then((d) => d.validation && setV(d)).catch(() => {}); }, []);
  const fa = v.validation, pw = v.validation_power;

  return (
    <main className="sheet methods">
      <section className="frame hero hero-sm">
        <div className="bar-top"><span className="tag">[METHODS] How the Detective decides</span><span className="tag">[PROOF] synthetic data, known answers</span></div>
        <h1 className="hero-line">Real change, <span className="hl">or natural noise?</span></h1>
        <p className="lede">Is this variable really changing here, or is it natural ups and downs? If it is changing, how fast, and how sure are we? If we can't tell yet, how long until we could?</p>
      </section>

      <Reveal className="frame proof">
        <Panel letter="a" height={220} yDomain={[0, 60]} xTicks={fa.phis} xFmt={(x) => x.toFixed(2)} yLabel="%"
          title={<>False alarms when there is <strong>no</strong> real trend ({fa.n_sims} synthetic series per point), against how "sticky" the noise is. The ideal is 5%.</>}
          series={[
            { xs: fa.phis, ys: fa.phis.map(() => 5), cls: "s-target" },
            { xs: fa.phis, ys: pct(fa.false_alarm_rate.naive_ols_anomalies), cls: "s-naive" },
            { xs: fa.phis, ys: pct(fa.false_alarm_rate.ours_verdict), cls: "s-ours" },
          ]}>
          <p className="key"><span><i className="sw sw-naive" />Naive test (ignores stickiness)</span><span><i className="sw sw-ours" />Our verdict</span><span><i className="sw sw-target" />5% target</span></p>
        </Panel>
        <Panel letter="b" height={220} yDomain={[0, 100]} xTicks={pw.trends_per_decade} xFmt={(x) => x.toFixed(1)} yLabel="%"
          title={<>How often a <strong>real</strong> trend is caught ({pw.n_sims} series per point), against the true trend per decade (noise SD 1).</>}
          series={[
            { xs: pw.trends_per_decade, ys: pct(pw.detection_rate.naive_ols_anomalies), cls: "s-naive" },
            { xs: pw.trends_per_decade, ys: pct(pw.detection_rate.ours_verdict), cls: "s-ours" },
            { xs: pw.trends_per_decade, ys: pct(pw.detection_rate.baseline_raw_ols), cls: "s-base" },
          ]}>
          <p className="key"><span><i className="sw sw-naive" />Naive test</span><span><i className="sw sw-ours" />Our verdict</span><span><i className="sw sw-base" />Straight line on raw monthly data</span></p>
        </Panel>
      </Reveal>
      <p className="cite">Fig. 3 | Proof it works, on synthetic data where we know the answer. The naive test finds trends that do not exist (up to {Math.round(Math.max(...fa.false_alarm_rate.naive_ols_anomalies) * 100)}% of the time). The raw straight line almost never raises a false alarm but misses real trends because the seasons drown them. Ours stays near 5% and still catches real trends.</p>

      <article className="frame prose">
        <h2>1. The evidence</h2>
        <p>NASA POWER (NASA Langley Research Center) serves NASA's MERRA-2 reanalysis and CERES / GEWEX SRB satellite data, monthly from January 1981 to December 2025. For a box we average every NASA grid cell inside it (0.5° × 0.625°), weighted by area.</p>

        <h2>2. Remove the seasons</h2>
        <p>Lincoln's temperature swings about 13 °C between winter and summer, while the long-term change is about 1.5 °C. We subtract each calendar month's 45-year average. What is left, the anomaly, is the part that can show a trend.</p>

        <h2>3. Two different tests, both corrected for sticky noise</h2>
        <p>A warm month tends to be followed by another warm month. Standard tests assume months are independent, so they become over-confident. We run Mann-Kendall with the Hamed &amp; Rao (1998) correction, and a least-squares t-test with an effective sample size. They share the same data, so they are not independent evidence. Requiring both guards against one test's assumptions driving the verdict. The rate is Sen's slope, per decade, with a 95% range.</p>

        <h2>4. The verdict</h2>
        <table className="rules">
          <thead><tr><th scope="col">Verdict</th><th scope="col">Rule</th></tr></thead>
          <tbody>
            <tr><td><span className="verdict v-strong"><span className="verdict-swatch" aria-hidden />Strong evidence</span></td><td>Both corrected tests p &lt; 0.01</td></tr>
            <tr><td><span className="verdict v-some"><span className="verdict-swatch" aria-hidden />Some evidence</span></td><td>Both corrected tests p &lt; 0.05</td></tr>
            <tr><td><span className="verdict v-mixed"><span className="verdict-swatch" aria-hidden />Mixed</span></td><td>One test p &lt; 0.05, the other not</td></tr>
            <tr><td><span className="verdict v-not_yet"><span className="verdict-swatch" aria-hidden />Not significant yet</span></td><td>Neither passes, but if today's rate is real it would show within 100 years of data</td></tr>
            <tr><td><span className="verdict v-none"><span className="verdict-swatch" aria-hidden />No trend detected</span></td><td>Neither passes, and a change this small would take more than 100 years to show. Absence of evidence, not proof that nothing is changing.</td></tr>
          </tbody>
        </table>

        <h2>5. Maps: many tests at once</h2>
        <p>Testing 150 grid cells at the 5% level gives about 7 "significant" cells by pure chance. We control the false discovery rate with Benjamini &amp; Hochberg (1995) at q = 0.10, as Wilks (2016) recommends for climate maps. Root-zone soil wetness over England and Wales: a typical analysis flags 89 of 137 cells, the corrected tests flag 18 on their own, and 0 survive the correction.</p>

        <h2>6. Second witness</h2>
        <p>Where we can, we check NASA against another record. <strong>Confirmed</strong>: an independent record (Met Office HadCET thermometers, ESA CCI satellite soil moisture) proves the same trend. <strong>Consistent</strong>: both find no proven trend, or the other record shares input data with MERRA-2 (NASA GPCP rainfall). <strong>Caution</strong>: they disagree. Central England temperature: HadCET +0.31 °C per decade, MERRA-2 +0.32, monthly agreement 0.99.</p>

        <h2>7. How long until we would know</h2>
        <p>For trends that are not significant yet we estimate the years of data needed to detect a trend of today's size, following Weatherhead et al. (1998). Today's rate is itself uncertain, so this is a guide to scale, not a forecast.</p>

        <h2>What this does not tell you</h2>
        <ul>
          <li>Trend is not cause. We detect change; we do not attribute it.</li>
          <li>MERRA-2 is a reanalysis: a model constrained by observations. Soil wetness and evaporation are model estimates.</li>
          <li>A straight-line trend summarises 45 years; real change can speed up, slow down or jump.</li>
          <li>Grid cells are about 50 km across. Your street may differ.</li>
        </ul>

        <h2>References</h2>
        <ul className="refs">
          <li>Benjamini, Y. &amp; Hochberg, Y. (1995). Controlling the false discovery rate. <i>J. R. Stat. Soc. B</i> 57, 289–300.</li>
          <li>Gilbert, R. O. (1987). <i>Statistical Methods for Environmental Pollution Monitoring</i>. Van Nostrand Reinhold.</li>
          <li>Hamed, K. H. &amp; Rao, A. R. (1998). A modified Mann-Kendall trend test for autocorrelated data. <i>J. Hydrology</i> 204, 182–196.</li>
          <li>Kendall, M. G. (1975). <i>Rank Correlation Methods</i>. Griffin.</li>
          <li>Mann, H. B. (1945). Nonparametric tests against trend. <i>Econometrica</i> 13, 245–259.</li>
          <li>Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. <i>JASA</i> 63, 1379–1389.</li>
          <li>Weatherhead, E. C. et al. (1998). Factors affecting the detection of trends. <i>J. Geophys. Res.</i> 103(D14), 17149–17161.</li>
          <li>Wilks, D. S. (2016). "The stippling shows statistically significant grid points". <i>BAMS</i> 97, 2263–2273.</li>
          <li>Yue, S. &amp; Wang, C. (2004). The Mann-Kendall test modified by effective sample size. <i>Water Resour. Manage.</i> 18, 201–218.</li>
          <li>NASA POWER Project, <a href="https://power.larc.nasa.gov">power.larc.nasa.gov</a>. Gelaro, R. et al. (2017), MERRA-2, <i>J. Climate</i> 30, 5419–5454.</li>
        </ul>

        <h2>AI use</h2>
        <p>Code was drafted with help from Claude (Anthropic) during the hackathon, and the team checked it with tests and synthetic experiments. Verdict numbers are always computed by code, never by AI.</p>
      </article>
    </main>
  );
}
