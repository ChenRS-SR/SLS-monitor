#ifndef PLANCK_H
#define PLANCK_H
#ifdef WIN32
#include <windows.h>
#else
#ifndef WINAPI
#define WINAPI
#endif
#endif

extern "C" {

	void WINAPI CalculateFromFactoryLUT_SH(
		double toEmissivity,
		double toReflectedTemperature,
		double toAtmosphericTemperature,
		double toDistance,
		double toRelativeHumidity,
		double toExternalOpticsTransmission,
		double toExternalOpticsTemperature,
		float* values, int from, int to);
};
#endif