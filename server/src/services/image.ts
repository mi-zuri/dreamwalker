import { GoogleGenAI } from "@google/genai";
import { generateCacheKey, getCachedImage, cacheImage } from "./cache.js";

const ai = new GoogleGenAI({ apiKey: process.env.GOOGLE_API_KEY! });

interface ImageGenerationParams {
  visualStyle: string;
  locationDescription: string;
  storyContext: string;
}

export async function generateSceneImage(
  params: ImageGenerationParams,
): Promise<string> {
  const { visualStyle, locationDescription, storyContext } = params;

  const cacheInput = `${visualStyle}|${locationDescription}|${storyContext}`;
  const cacheKey = generateCacheKey(cacheInput);

  // Check cache first
  const cachedPath = await getCachedImage(cacheKey);
  if (cachedPath) {
    console.log(`🎨 Image cache hit: ${cacheKey.slice(0, 12)}...`);
    return `/api/media/images/${cacheKey}`;
  }

  console.log(`🎨 Generating image via Gemini...`);

  const prompt = `Generate an image: ${visualStyle}. ${locationDescription}. Scene: ${storyContext}`;

  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash-image",
    contents: prompt,
    config: { responseModalities: ["IMAGE"] },
  });

  const imagePart = response.candidates?.[0]?.content?.parts?.find(
    (p: any) => p.inlineData,
  );
  if (!imagePart?.inlineData?.data) {
    throw new Error("No image data returned from Gemini");
  }

  const buffer = Buffer.from(imagePart.inlineData.data, "base64");
  await cacheImage(cacheKey, buffer);

  console.log(`🎨 Image cached: ${cacheKey.slice(0, 12)}...`);
  return `/api/media/images/${cacheKey}`;
}
