import { GoogleGenAI } from "@google/genai";
import { generateCacheKey, getCachedMedia, cacheMedia } from "./cache.js";
import { logAI } from "./ai-log.js";

const ai = new GoogleGenAI({ apiKey: process.env.GOOGLE_API_KEY! });

export async function generateSceneImage(
  visualStyle: string,
  locationDescription: string,
  storyContext: string,
): Promise<string> {
  const cacheKey = generateCacheKey(`${visualStyle}|${locationDescription}|${storyContext}`);
  const prompt = `Generate an image: ${visualStyle}. ${locationDescription}. Scene: ${storyContext}`;

  if (await getCachedMedia('image', cacheKey)) {
    logAI('image', prompt, `<cached ${cacheKey}>`);
    return `/api/media/images/${cacheKey}`;
  }

  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash-image",
    contents: prompt,
    config: { responseModalities: ["IMAGE"] },
  });

  const inlineData = response.candidates?.[0]?.content?.parts?.find((p: any) => p.inlineData)?.inlineData;
  if (!inlineData?.data) throw new Error("No image data returned from Gemini");

  const buffer = Buffer.from(inlineData.data, "base64");
  logAI('image', prompt, `<image ${Math.round(buffer.length / 1024)}KB → ${cacheKey}>`);

  await cacheMedia('image', cacheKey, buffer);
  return `/api/media/images/${cacheKey}`;
}
