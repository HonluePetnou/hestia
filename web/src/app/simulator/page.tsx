"use client";

import dynamic from "next/dynamic";
import { useState, type FormEvent } from "react";

import { Loading, PageHeader } from "@/components/ui";

// WebGL only exists in the browser, so the canvas is never server-rendered.
const DropletScene = dynamic(() => import("@/components/DropletScene"), {
  ssr: false,
  loading: () => <Loading />,
});

interface PredictRequest {
  fuel: string;
  pressure_atm: number;
  o2_mole_fraction: number;
  co2_mole_fraction: number;
  initial_diameter_mm: number;
}

interface PredictResponse {
  burn_rate_k: number;
  extinction_probability: number;
  burn_time_s: number;
  model: string;
  mae_mm2_s: number | null;
  out_of_range: boolean;
  warnings: string[];
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function Page() {
  const [form, setForm] = useState<PredictRequest>({
    fuel: "n-heptane",
    pressure_atm: 1.0,
    o2_mole_fraction: 0.21,
    co2_mole_fraction: 0.0,
    initial_diameter_mm: 3.0,
  });

  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Submit combustion parameters to the FastAPI /predict endpoint
  async function handlePredict(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        const errBody = await response.text();
        throw new Error(`API error (${response.status}): ${errBody}`);
      }

      const data: PredictResponse = await response.json();
      setPrediction(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to reach the prediction backend."
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="3D Droplet Flame Simulator"
        subtitle="Microgravity droplet combustion prediction powered by FLEX ML models."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* 3D Canvas & ML Prediction Results */}
        <div className="space-y-4 lg:col-span-7">
          <div className="h-[440px] w-full rounded border border-gray-200">
            <DropletScene />
          </div>

          {error && (
            <div className="rounded border border-red-300 bg-red-50 p-4 text-sm text-red-800">
              <p className="font-semibold">Backend Connection Error</p>
              <p className="mt-1">{error}</p>
            </div>
          )}

          {prediction && (
            <div className="space-y-4 rounded border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-700">
                  Combustion Prediction
                </h2>
                <span className="rounded bg-gray-100 px-2 py-0.5 font-mono text-xs text-gray-700">
                  {prediction.model}
                  {prediction.mae_mm2_s !== null
                    ? ` (MAE: +/-${prediction.mae_mm2_s} mm2/s)`
                    : ""}
                </span>
              </div>

              {/* Out-of-bounds warning banner when inputs exceed FLEX experimental ranges */}
              {prediction.out_of_range && (
                <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                  <p className="font-semibold">
                    Out-of-Range Warning (Extrapolated)
                  </p>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
                    {prediction.warnings.map((warning, idx) => (
                      <li key={idx}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded border border-gray-100 bg-gray-50 p-3">
                  <p className="text-xs text-gray-500">Burn Rate (K)</p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">
                    {prediction.burn_rate_k}{" "}
                    <span className="text-xs font-normal text-gray-500">
                      mm2/s
                    </span>
                  </p>
                </div>

                <div className="rounded border border-gray-100 bg-gray-50 p-3">
                  <p className="text-xs text-gray-500">Burn Time (d0^2 / K)</p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">
                    {prediction.burn_time_s}{" "}
                    <span className="text-xs font-normal text-gray-500">s</span>
                  </p>
                </div>

                <div className="rounded border border-gray-100 bg-gray-50 p-3">
                  <p className="text-xs text-gray-500">
                    Extinction Probability
                  </p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">
                    {(prediction.extinction_probability * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Simulation Input Form */}
        <form
          onSubmit={handlePredict}
          className="h-fit space-y-4 rounded border border-gray-200 bg-white p-5 lg:col-span-5"
        >
          <h2 className="text-base font-semibold text-gray-900">
            Chamber & Fuel Parameters
          </h2>

          <div>
            <label
              htmlFor="fuel"
              className="block text-sm font-medium text-gray-700"
            >
              Fuel
            </label>
            <input
              id="fuel"
              list="flex-fuels"
              type="text"
              required
              value={form.fuel}
              onChange={(e) => setForm({ ...form, fuel: e.target.value })}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
              placeholder="e.g. n-heptane or kerosene"
            />
            <datalist id="flex-fuels">
              <option value="n-heptane" />
              <option value="methanol" />
              <option value="ethanol" />
              <option value="n-decane" />
              <option value="n-octane" />
            </datalist>
          </div>

          <div>
            <label
              htmlFor="pressure_atm"
              className="block text-sm font-medium text-gray-700"
            >
              Ambient Pressure (atm)
            </label>
            <input
              id="pressure_atm"
              type="number"
              step="0.05"
              min="0.01"
              required
              value={form.pressure_atm}
              onChange={(e) =>
                setForm({
                  ...form,
                  pressure_atm: parseFloat(e.target.value) || 0,
                })
              }
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="o2_mole_fraction"
              className="block text-sm font-medium text-gray-700"
            >
              O2 Mole Fraction (0 - 1)
            </label>
            <input
              id="o2_mole_fraction"
              type="number"
              step="0.01"
              min="0"
              max="1"
              required
              value={form.o2_mole_fraction}
              onChange={(e) =>
                setForm({
                  ...form,
                  o2_mole_fraction: parseFloat(e.target.value) || 0,
                })
              }
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="co2_mole_fraction"
              className="block text-sm font-medium text-gray-700"
            >
              CO2 Mole Fraction (0 - 1)
            </label>
            <input
              id="co2_mole_fraction"
              type="number"
              step="0.01"
              min="0"
              max="1"
              required
              value={form.co2_mole_fraction}
              onChange={(e) =>
                setForm({
                  ...form,
                  co2_mole_fraction: parseFloat(e.target.value) || 0,
                })
              }
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="initial_diameter_mm"
              className="block text-sm font-medium text-gray-700"
            >
              Initial Droplet Diameter d0 (mm)
            </label>
            <input
              id="initial_diameter_mm"
              type="number"
              step="0.1"
              min="0.1"
              required
              value={form.initial_diameter_mm}
              onChange={(e) =>
                setForm({
                  ...form,
                  initial_diameter_mm: parseFloat(e.target.value) || 0,
                })
              }
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded bg-gray-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800 disabled:opacity-50"
          >
            {isLoading ? "Running ML Prediction..." : "Run Prediction"}
          </button>
        </form>
      </div>
    </>
  );
}