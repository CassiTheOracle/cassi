import { type FC } from 'react'

import { cn } from '@/lib/utils'

import { PARAGRAPH_SIZES } from './constants.js'
import { type ParagraphProps } from './types.js'

const Paragraph: FC<ParagraphProps> = ({
  children,
  size = 'default',
  className,
  id
}) => (
  <p id={id} className={cn(PARAGRAPH_SIZES[size], className)}>
    {children}
  </p>
)

export default Paragraph
