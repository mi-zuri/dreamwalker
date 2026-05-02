import { GoogleGenAI } from "@google/genai";
import { generateCacheKey, getCachedMedia, cacheMedia } from "./cache.js";

const ai = new GoogleGenAI({ apiKey: process.env.GOOGLE_API_KEY! });

export async function generateSceneImage(
  visualStyle: string,
  locationDescription: string,
  storyContext: string,
): Promise<string> {
  const cacheKey = generateCacheKey(`${visualStyle}|${locationDescription}|${storyContext}`);

  if (await getCachedMedia('image', cacheKey)) return `/api/media/images/${cacheKey}`;

  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash-image",
    contents: `Generate an image: ${visualStyle}. ${locationDescription}. Scene: ${storyContext}`,
    config: { responseModalities: ["IMAGE"] },
  });

  const inlineData = response.candidates?.[0]?.content?.parts?.find((p: any) => p.inlineData)?.inlineData;
  if (!inlineData?.data) throw new Error("No image data returned from Gemini");

  await cacheMedia('image', cacheKey, Buffer.from(inlineData.data, "base64"));
  return `/api/media/images/${cacheKey}`;
}
