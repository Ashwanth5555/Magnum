import { useState } from 'react'
import { tileClass } from '../lib/format'

/**
 * A product shot, with the painted tile as its floor.
 *
 * The tiles were always a stand-in for photography that did not exist yet. Now
 * that it does, the tile stays underneath as the loading and failure state, so
 * a missing file degrades to the old look instead of a broken-image glyph in
 * front of a client.
 */
export default function ProductImage({
  sku, name, category, flavour, className = '', rounded = 'rounded-xl',
}: {
  sku: string
  name?: string
  category: string
  flavour?: string | null
  className?: string
  rounded?: string
}) {
  const [failed, setFailed] = useState(false)
  return (
    <span
      className={`tile relative block overflow-hidden ${rounded} ${tileClass({ category, flavour })} ${className}`}
    >
      {!failed && (
        <img
          src={`/products/${sku.toLowerCase()}.webp`}
          alt={name ?? sku}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}
    </span>
  )
}
